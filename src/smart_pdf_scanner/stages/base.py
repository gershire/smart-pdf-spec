"""ProcessingStage base interface and ValidationWarning model.

Defines the abstract contract that all pipeline stage implementations must
follow (Requirement 1: Pipeline Orchestration).

Stage implementations live in sibling modules:
- ``pdf_parser.py``          — raw PDF extraction
- ``layout_analyzer.py``     — layout detection and classification
- ``ocr_processor.py``       — OCR on image-based pages
- ``structure_recognizer.py``— heading hierarchy and reading order
- ``table_processor.py``     — table extraction and Markdown conversion
- ``image_processor.py``     — image classification and description
- ``semantic_enhancer.py``   — LLM-driven semantic refinement (optional)
- ``markdown_generator.py``  — final Markdown assembly and output
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from pydantic import BaseModel

from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document

__all__ = ["ValidationWarning", "WarningSeverity", "ProcessingStage"]


class WarningSeverity(str, Enum):
    """Severity level for a :class:`ValidationWarning`."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationWarning(BaseModel):
    """A non-fatal issue detected during stage validation or processing.

    Warnings are accumulated on :attr:`~smart_pdf_scanner.models.document.Document.processing_warnings`
    and reported in the pipeline result without halting execution (unless
    severity is ``ERROR`` and the pipeline is configured to be strict).

    Attributes:
        code: Short machine-readable identifier for the warning type
            (e.g. ``"low_ocr_confidence"``, ``"missing_text_layer"``).
        message: Human-readable description of the issue.
        severity: Severity level; defaults to ``WARNING``.
        page_number: Optional page number the warning applies to.
        element_id: Optional element identifier the warning applies to.
    """

    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING
    page_number: int | None = None
    element_id: str | None = None


class ProcessingStage(ABC):
    """Abstract base class for all pipeline processing stages.

    Each stage receives a :class:`~smart_pdf_scanner.models.document.Document`
    (which may be partially populated by earlier stages) and the global
    :class:`~smart_pdf_scanner.models.config.Config`, transforms it in place or
    returns a new document, and returns the result.

    Stages are run in order by the
    :class:`~smart_pdf_scanner.core.pipeline.Pipeline` orchestrator.  A stage
    may call :meth:`validate` before :meth:`process` to surface pre-condition
    warnings; the orchestrator accumulates these on
    :attr:`~smart_pdf_scanner.models.document.Document.processing_warnings`.

    Implementing a new stage requires:
    1. Subclass :class:`ProcessingStage`.
    2. Implement :meth:`process` to transform the document.
    3. Implement :meth:`validate` to check pre-conditions (return ``[]`` if
       none apply).
    4. Expose a unique stage identifier via the :attr:`name` property.

    Example::

        class MyStage(ProcessingStage):
            @property
            def name(self) -> str:
                return "my_stage"

            def process(self, document, config):
                # transform document ...
                return document

            def validate(self, document, config):
                warnings = []
                if not document.pages:
                    warnings.append(ValidationWarning(
                        code="no_pages",
                        message="Document has no pages to process.",
                    ))
                return warnings
    """

    @abstractmethod
    def process(self, document: Document, config: Config) -> Document:
        """Run this stage on *document* and return the transformed result.

        Implementations may mutate *document* in place and return it, or
        return a new :class:`~smart_pdf_scanner.models.document.Document`.

        Args:
            document: The document to process.  May be partially populated
                by earlier pipeline stages.
            config: The active pipeline configuration.

        Returns:
            The processed (possibly mutated) document.

        Raises:
            Exception: Stage-specific exceptions on unrecoverable errors;
                the pipeline will catch these and decide whether to abort or
                continue with partial results.
        """

    @abstractmethod
    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        """Check pre-conditions and return any warnings.

        Called by the pipeline before :meth:`process`.  Warnings do not
        prevent :meth:`process` from running; they are accumulated on
        :attr:`~smart_pdf_scanner.models.document.Document.processing_warnings`.

        Args:
            document: The document in its current state.
            config: The active pipeline configuration.

        Returns:
            A list of :class:`ValidationWarning` objects describing any
            issues found.  Return an empty list if all pre-conditions are met.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage identifier used in logging, progress events, and config."""
