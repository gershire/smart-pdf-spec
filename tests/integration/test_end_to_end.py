"""End-to-end integration tests for the full pipeline (task 7.5).

These tests use real PDFs created with PyMuPDF (fitz) and run the full
pipeline with real stage implementations (no mocks).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smart_pdf_scanner.core.pipeline import Pipeline, PipelineBuilder
from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
from smart_pdf_scanner.models.config import Config, ProcessingMode
from smart_pdf_scanner.stages.layout_analyzer import LayoutAnalyzer
from smart_pdf_scanner.stages.markdown_generator import MarkdownGenerator
from smart_pdf_scanner.stages.pdf_parser import PDFParser
from smart_pdf_scanner.stages.structure_recognizer import StructureRecognizer


# ---------------------------------------------------------------------------
# PDF fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def simple_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Single-page PDF with title and body text."""
    fitz = pytest.importorskip("fitz")
    tmp = tmp_path_factory.mktemp("pdfs")
    path = tmp / "simple.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 80), "Introduction", fontsize=24)
    page.insert_text((72, 130), "This is the first paragraph.", fontsize=12)
    page.insert_text((72, 155), "This is the second paragraph.", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="module")
def structured_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Multi-section PDF with headings and body text."""
    fitz = pytest.importorskip("fitz")
    tmp = tmp_path_factory.mktemp("pdfs")
    path = tmp / "structured.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 50), "Document Title", fontsize=28)
    page.insert_text((72, 120), "1. Introduction", fontsize=18)
    page.insert_text((72, 155), "Background information about the topic.", fontsize=12)
    page.insert_text((72, 220), "2. Methods", fontsize=18)
    page.insert_text((72, 255), "We used the following approach.", fontsize=12)
    page.insert_text((72, 320), "3. Results", fontsize=18)
    page.insert_text((72, 355), "Our results show the following findings.", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# Basic pipeline validation
# ---------------------------------------------------------------------------


class TestPipelineWithRealPDF:
    def test_pdf_parser_extracts_pages(self, simple_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.models.document import Document
        from smart_pdf_scanner.models.metadata import DocumentMetadata

        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        result = PDFParser(pdf_path=simple_pdf).process(doc, Config())
        assert len(result.pages) == 1
        elements = result.get_all_elements()
        texts = [getattr(el, "text", "") for el in elements]
        assert any("Introduction" in t for t in texts)

    def test_layout_analyzer_runs_on_parsed_doc(self, simple_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.models.document import Document
        from smart_pdf_scanner.models.metadata import DocumentMetadata

        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        doc = PDFParser(pdf_path=simple_pdf).process(doc, Config())
        doc = LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, Config())
        assert doc.pages[0].elements  # at least something detected

    def test_structure_recognizer_finds_heading(self, simple_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.models.document import Document
        from smart_pdf_scanner.models.metadata import DocumentMetadata

        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        config = Config()
        doc = PDFParser(pdf_path=simple_pdf).process(doc, config)
        doc = LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, config)
        doc = StructureRecognizer().process(doc, config)
        assert doc.structure is not None
        assert len(doc.structure.headings) >= 1

    def test_markdown_generator_produces_output(self, simple_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.models.document import Document
        from smart_pdf_scanner.models.metadata import DocumentMetadata

        out_path = tmp_path / "output.md"
        doc = Document(
            metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
            assets_folder=tmp_path / "assets",
        )
        config = Config(include_page_numbers=False)
        doc = PDFParser(pdf_path=simple_pdf).process(doc, config)
        doc = LayoutAnalyzer(primary_engine=HeuristicEngine()).process(doc, config)
        doc = StructureRecognizer().process(doc, config)
        doc = MarkdownGenerator(output_path=out_path).process(doc, config)
        assert out_path.exists()
        content = out_path.read_text()
        assert content.strip()  # non-empty output


# ---------------------------------------------------------------------------
# Pipeline orchestrator tests
# ---------------------------------------------------------------------------


class TestPipelineOrchestrator:
    def test_pipeline_with_minimal_stages(self, simple_pdf: Path, tmp_path: Path) -> None:
        stages = [
            PDFParser(),
            LayoutAnalyzer(primary_engine=HeuristicEngine()),
            StructureRecognizer(),
            MarkdownGenerator(),
        ]
        config = Config(
            enabled_stages=["pdf_parser", "layout_analyzer", "structure_recognizer", "markdown_generator"],
            include_page_numbers=False,
        )
        pipeline = Pipeline(stages=stages, config=config)
        result = pipeline.process(simple_pdf, output_path=tmp_path / "out.md")
        assert result.success is True
        assert not result.errors

    def test_pipeline_produces_markdown_file(self, simple_pdf: Path, tmp_path: Path) -> None:
        stages = [
            PDFParser(),
            LayoutAnalyzer(primary_engine=HeuristicEngine()),
            StructureRecognizer(),
            MarkdownGenerator(),
        ]
        config = Config(
            enabled_stages=["pdf_parser", "layout_analyzer", "structure_recognizer", "markdown_generator"],
            include_page_numbers=False,
        )
        out_path = tmp_path / "result.md"
        Pipeline(stages=stages, config=config).process(simple_pdf, output_path=out_path)
        assert out_path.exists()
        assert out_path.read_text().strip()

    def test_pipeline_statistics_populated(self, simple_pdf: Path, tmp_path: Path) -> None:
        stages = [PDFParser(), MarkdownGenerator()]
        config = Config(enabled_stages=["pdf_parser", "markdown_generator"])
        result = Pipeline(stages=stages, config=config).process(simple_pdf)
        assert result.statistics is not None
        assert result.statistics.processing_time_seconds >= 0

    def test_structured_pdf_headings_in_output(self, structured_pdf: Path, tmp_path: Path) -> None:
        out_path = tmp_path / "structured.md"
        stages = [
            PDFParser(),
            LayoutAnalyzer(primary_engine=HeuristicEngine()),
            StructureRecognizer(),
            MarkdownGenerator(output_path=out_path),
        ]
        config = Config(
            enabled_stages=["pdf_parser", "layout_analyzer", "structure_recognizer", "markdown_generator"],
            include_page_numbers=False,
        )
        result = Pipeline(stages=stages, config=config).process(structured_pdf)
        assert result.success
        content = out_path.read_text()
        assert "#" in content  # some headings


# ---------------------------------------------------------------------------
# Processing mode presets
# ---------------------------------------------------------------------------


class TestProcessingModePresets:
    def test_fast_mode_pipeline_builds(self) -> None:
        builder = PipelineBuilder.from_preset(ProcessingMode.FAST)
        pipeline = builder.build()
        assert isinstance(pipeline, Pipeline)
        assert pipeline._config.llm_provider is None

    def test_balanced_mode_pipeline_builds(self) -> None:
        builder = PipelineBuilder.from_preset(ProcessingMode.BALANCED)
        pipeline = builder.build()
        assert isinstance(pipeline, Pipeline)

    def test_high_fidelity_mode_pipeline_builds(self) -> None:
        builder = PipelineBuilder.from_preset(ProcessingMode.HIGH_FIDELITY)
        pipeline = builder.build()
        assert isinstance(pipeline, Pipeline)
        assert pipeline._config.llm_provider is not None
