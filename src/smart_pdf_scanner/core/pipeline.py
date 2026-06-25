"""Pipeline orchestrator and builder.

Implements :class:`Pipeline`, which executes processing stages sequentially
with input validation, progress tracking, and graceful failure handling
(Requirement 1: Pipeline Orchestration), and :class:`PipelineBuilder`, which
constructs a fully-configured :class:`Pipeline` from a :class:`Config`
instance or a processing-mode preset.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from smart_pdf_scanner.models.config import Config, ProcessingMode
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import ElementType
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.result import ProcessingResult, ProcessingStatistics
from smart_pdf_scanner.stages.base import ProcessingStage, WarningSeverity

__all__ = ["Pipeline", "PipelineBuilder", "ProgressEvent"]

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF"


@dataclass
class ProgressEvent:
    """Emitted before and after each stage to report pipeline progress.

    Attributes:
        stage_name: The :attr:`~smart_pdf_scanner.stages.base.ProcessingStage.name`
            of the stage being executed.
        stage_index: Zero-based index of the stage within the active stage list.
        total_stages: Total number of active stages in this run.
        status: Either ``"started"`` or ``"completed"``.
        fraction: Completion fraction in ``[0.0, 1.0]`` (``stage_index / total_stages``).
    """

    stage_name: str
    stage_index: int
    total_stages: int
    status: str
    fraction: float


ProgressCallback = Callable[[ProgressEvent], None]


class Pipeline:
    """Orchestrates sequential execution of processing stages.

    Stages are executed in the order provided; stages whose
    :attr:`~smart_pdf_scanner.stages.base.ProcessingStage.name` is absent from
    :attr:`~smart_pdf_scanner.models.config.Config.enabled_stages` are skipped.

    When a stage raises an exception the error is recorded and processing
    continues with the next stage (partial-processing semantics).  The
    :attr:`~smart_pdf_scanner.models.result.ProcessingResult.success` flag is
    set to ``False`` whenever any stage fails.

    Args:
        stages: Ordered list of stage instances to execute.
        config: Active pipeline configuration.
        on_progress: Optional callback invoked before and after each stage.
    """

    def __init__(
        self,
        stages: List[ProcessingStage],
        config: Config,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        self._stages = stages
        self._config = config
        self._on_progress = on_progress

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        pdf_path: Path,
        output_path: Optional[Path] = None,
    ) -> ProcessingResult:
        """Process a PDF through all configured stages.

        Args:
            pdf_path: Path to the source PDF file.
            output_path: Optional path for the generated Markdown file.  When
                omitted the Markdown is stored on the document for programmatic
                use but not written to disk (unless a stage was constructed with
                an explicit output path).

        Returns:
            :class:`~smart_pdf_scanner.models.result.ProcessingResult` describing
            the outcome, collected warnings and errors, and processing statistics.
        """
        start_time = datetime.now(timezone.utc)
        wall_start = time.monotonic()

        # --- Input validation -------------------------------------------
        errors = self.validate_input(pdf_path)
        if errors:
            return self._make_result(
                success=False,
                document=None,
                output_path=None,
                assets_folder=None,
                warnings=[],
                errors=errors,
                wall_start=wall_start,
                start_time=start_time,
            )

        # --- Initial document -------------------------------------------
        assets_folder = self._assets_folder(pdf_path, output_path)
        document = Document(
            metadata=DocumentMetadata(
                page_count=0,
                file_size_bytes=pdf_path.stat().st_size,
            ),
            assets_folder=assets_folder,
        )
        # Stash paths for stages that look them up via getattr()
        object.__setattr__(document, "_pdf_path", str(pdf_path))
        if output_path is not None:
            object.__setattr__(document, "_output_path", output_path)

        # --- Stage execution -------------------------------------------
        enabled = set(self._config.enabled_stages)
        active = [s for s in self._stages if s.name in enabled]
        total = len(active)

        all_warnings: list[str] = []
        all_errors: list[str] = []
        success = True

        for idx, stage in enumerate(active):
            self._emit(stage.name, idx, total, "started")

            # Validate pre-conditions
            try:
                stage_warnings = stage.validate(document, self._config)
            except Exception as exc:
                logger.exception("Stage '%s': validate() raised an exception", stage.name)
                all_errors.append(f"[{stage.name}] validation error: {exc}")
                stage_warnings = []

            for w in stage_warnings:
                msg = f"[{stage.name}] {w.code}: {w.message}"
                all_warnings.append(msg)
                document.processing_warnings.append(msg)
                if w.severity == WarningSeverity.ERROR:
                    all_errors.append(msg)

            # Execute the stage
            try:
                document = stage.process(document, self._config)
            except Exception as exc:
                logger.exception("Stage '%s': process() raised an exception", stage.name)
                error_msg = f"[{stage.name}] processing failed: {exc}"
                all_errors.append(error_msg)
                document.processing_warnings.append(error_msg)
                success = False

            self._emit(stage.name, idx + 1, total, "completed")

        # --- Collect statistics ----------------------------------------
        all_elements = document.get_all_elements()
        tables = sum(1 for e in all_elements if e.element_type == ElementType.TABLE)
        images = sum(1 for e in all_elements if e.element_type == ElementType.IMAGE)
        stats = ProcessingStatistics(
            total_pages=document.metadata.page_count,
            pages_processed=len(document.pages),
            elements_detected=len(all_elements),
            tables_extracted=tables,
            images_extracted=images,
            processing_time_seconds=time.monotonic() - wall_start,
            start_time=start_time,
            end_time=datetime.now(timezone.utc),
        )

        # Resolve the final markdown path (may have been set by MarkdownGenerator)
        resolved_md = output_path or _getattr_path(document, "_output_path")
        resolved_assets = assets_folder if assets_folder.exists() else None

        return ProcessingResult(
            success=success and not all_errors,
            document=document,
            markdown_path=resolved_md,
            assets_folder=resolved_assets,
            warnings=all_warnings,
            errors=all_errors,
            statistics=stats,
        )

    def validate_input(self, pdf_path: Path) -> list[str]:
        """Validate the input PDF file before processing.

        Checks that the file exists, is readable, starts with a PDF magic
        header, and does not exceed the configured size limit.

        Args:
            pdf_path: Path to validate.

        Returns:
            A list of human-readable error strings.  Empty when valid.
        """
        errors: list[str] = []

        if not pdf_path.exists():
            errors.append(f"File not found: {pdf_path}")
            return errors

        if not pdf_path.is_file():
            errors.append(f"Path is not a regular file: {pdf_path}")
            return errors

        try:
            with pdf_path.open("rb") as fh:
                header = fh.read(4)
        except OSError as exc:
            errors.append(f"Cannot read file: {exc}")
            return errors

        if header != _PDF_MAGIC:
            errors.append(f"File does not appear to be a valid PDF (bad magic): {pdf_path}")

        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > self._config.max_file_size_mb:
            errors.append(
                f"File size ({size_mb:.1f} MB) exceeds the configured limit "
                f"({self._config.max_file_size_mb} MB)"
            )

        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(
        self, stage_name: str, stage_index: int, total_stages: int, status: str
    ) -> None:
        if self._on_progress is None:
            return
        fraction = stage_index / total_stages if total_stages else 0.0
        event = ProgressEvent(stage_name, stage_index, total_stages, status, fraction)
        try:
            self._on_progress(event)
        except Exception:
            logger.debug("Progress callback raised an exception", exc_info=True)

    @staticmethod
    def _assets_folder(pdf_path: Path, output_path: Optional[Path]) -> Path:
        if output_path is not None:
            return output_path.parent / (output_path.stem + "_assets")
        return pdf_path.parent / (pdf_path.stem + "_assets")

    @staticmethod
    def _make_result(
        *,
        success: bool,
        document: Optional[Document],
        output_path: Optional[Path],
        assets_folder: Optional[Path],
        warnings: list[str],
        errors: list[str],
        wall_start: float,
        start_time: datetime,
    ) -> ProcessingResult:
        return ProcessingResult(
            success=success,
            document=document,
            markdown_path=output_path,
            assets_folder=assets_folder,
            warnings=warnings,
            errors=errors,
            statistics=ProcessingStatistics(
                total_pages=0,
                pages_processed=0,
                elements_detected=0,
                tables_extracted=0,
                images_extracted=0,
                processing_time_seconds=time.monotonic() - wall_start,
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
            ),
        )


def _getattr_path(obj: object, attr: str) -> Optional[Path]:
    """Retrieve a Path-valued attribute from *obj*, returning ``None`` if absent."""
    value = getattr(obj, attr, None)
    return Path(value) if value else None


# ---------------------------------------------------------------------------
# PipelineBuilder
# ---------------------------------------------------------------------------


class PipelineBuilder:
    """Constructs a configured :class:`Pipeline` from a :class:`Config`.

    Uses engine factory classes to instantiate the correct OCR, layout, and LLM
    engines and wires them into the appropriate processing stages.

    Args:
        config: Pipeline configuration to build from.

    Example::

        config = ConfigManager.load("config/balanced-mode.yaml")
        pipeline = PipelineBuilder(config).build()
        result = pipeline.process(Path("document.pdf"), Path("output.md"))
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    @classmethod
    def from_preset(cls, mode: ProcessingMode) -> "PipelineBuilder":
        """Create a :class:`PipelineBuilder` pre-configured for *mode*.

        Args:
            mode: The processing mode preset to use.

        Returns:
            A :class:`PipelineBuilder` ready to call :meth:`build`.
        """
        from smart_pdf_scanner.core.config import ConfigManager

        return cls(ConfigManager.get_preset(mode))

    def build(
        self, on_progress: Optional[ProgressCallback] = None
    ) -> Pipeline:
        """Build and return a :class:`Pipeline`.

        Instantiates engines via factory classes and constructs stage objects in
        the canonical stage order.  Only stages listed in
        :attr:`~smart_pdf_scanner.models.config.Config.enabled_stages` will
        execute when the pipeline runs.

        Args:
            on_progress: Optional progress callback forwarded to the
                :class:`Pipeline`.

        Returns:
            A ready-to-use :class:`Pipeline`.
        """
        from smart_pdf_scanner.engines.factories import (
            LayoutEngineFactory,
            LLMProviderFactory,
            OCREngineFactory,
        )
        from smart_pdf_scanner.stages.image_processor import ImageProcessor
        from smart_pdf_scanner.stages.layout_analyzer import LayoutAnalyzer
        from smart_pdf_scanner.stages.markdown_generator import MarkdownGenerator
        from smart_pdf_scanner.stages.ocr_processor import OCRProcessor
        from smart_pdf_scanner.stages.pdf_parser import PDFParser
        from smart_pdf_scanner.stages.semantic_enhancer import SemanticEnhancer
        from smart_pdf_scanner.stages.structure_recognizer import StructureRecognizer
        from smart_pdf_scanner.stages.table_processor import TableProcessor

        config = self._config
        enabled = set(config.enabled_stages)

        # Engines — only create what's needed by enabled stages
        needs_layout = "layout_analyzer" in enabled
        needs_ocr = "ocr_processor" in enabled or "image_processor" in enabled
        needs_llm = (
            "semantic_enhancer" in enabled or "image_processor" in enabled
        ) and config.llm_provider is not None

        layout_engine = LayoutEngineFactory.create(config) if needs_layout else None
        layout_fallback = LayoutEngineFactory.create_fallback(config) if needs_layout else None

        ocr_engine = OCREngineFactory.create(config) if needs_ocr else None
        ocr_fallback = OCREngineFactory.create_fallback(config) if needs_ocr else None

        llm_provider = LLMProviderFactory.create(config) if needs_llm else None

        # Build ordered stage list (canonical pipeline order)
        stages: List[ProcessingStage] = [
            PDFParser(),
            LayoutAnalyzer(
                primary_engine=layout_engine,  # type: ignore[arg-type]
                fallback_engine=layout_fallback,
            ),
            OCRProcessor(
                primary_engine=ocr_engine,  # type: ignore[arg-type]
                fallback_engine=ocr_fallback,
            ),
            StructureRecognizer(),
            TableProcessor(),
            ImageProcessor(ocr_engine=ocr_engine, llm_provider=llm_provider),
            SemanticEnhancer(llm_provider=llm_provider),
            MarkdownGenerator(),
        ]

        return Pipeline(stages=stages, config=config, on_progress=on_progress)
