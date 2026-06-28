"""Performance benchmarks for the Smart PDF Scanner pipeline (task 8.5).

These tests verify that processing time stays within acceptable bounds for
each processing mode. They require fitz (PyMuPDF) to generate synthetic PDFs
and are marked with ``@pytest.mark.slow`` so they can be excluded from the
normal CI suite with ``-m "not slow"``.

Target: 1–15 seconds per page depending on mode (no LLM / OCR-only runs).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Synthetic PDF fixtures
# ---------------------------------------------------------------------------


def _make_pdf(tmp_path: Path, page_count: int, title: str = "Benchmark PDF") -> Path:
    """Create a simple multi-page PDF with text."""
    fitz = pytest.importorskip("fitz")
    path = tmp_path / f"bench_{page_count}p.pdf"
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 80), f"{title} — Page {i + 1}", fontsize=18)
        for j in range(5):
            page.insert_text(
                (72, 130 + j * 30),
                f"Paragraph {j + 1}: The quick brown fox jumps over the lazy dog.",
                fontsize=12,
            )
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="module")
def one_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_pdf(tmp_path_factory.mktemp("bench"), 1)


@pytest.fixture(scope="module")
def five_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_pdf(tmp_path_factory.mktemp("bench"), 5)


@pytest.fixture(scope="module")
def ten_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_pdf(tmp_path_factory.mktemp("bench"), 10)


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------


def _run_fast_pipeline(pdf_path: Path, output_path: Path) -> float:
    """Run the fast-mode pipeline and return wall-clock seconds."""
    from smart_pdf_scanner.core.config import ConfigManager
    from smart_pdf_scanner.core.pipeline import PipelineBuilder
    from smart_pdf_scanner.models.config import ProcessingMode

    config = ConfigManager.get_preset(ProcessingMode.FAST)
    pipeline = PipelineBuilder(config).build()

    start = time.monotonic()
    result = pipeline.process(pdf_path, output_path=output_path)
    elapsed = time.monotonic() - start

    assert result.success or not result.errors, f"Pipeline failed: {result.errors}"
    return elapsed


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPipelineThroughput:
    """Verify pages-per-second throughput for the fast-mode pipeline."""

    def test_one_page_under_threshold(self, one_page_pdf: Path, tmp_path: Path) -> None:
        elapsed = _run_fast_pipeline(one_page_pdf, tmp_path / "out1.md")
        # Generous threshold — CI machines vary; just assert it doesn't hang
        assert elapsed < 30.0, f"1-page PDF took {elapsed:.2f}s (threshold 30s)"

    def test_five_pages_linear_scaling(
        self, one_page_pdf: Path, five_page_pdf: Path, tmp_path: Path
    ) -> None:
        t1 = _run_fast_pipeline(one_page_pdf, tmp_path / "out1.md")
        t5 = _run_fast_pipeline(five_page_pdf, tmp_path / "out5.md")
        # 5-page doc should take less than 10× the 1-page time
        assert t5 < t1 * 10 + 5.0, (
            f"5-page PDF ({t5:.2f}s) much slower than 10× 1-page ({t1:.2f}s × 10)"
        )

    def test_ten_pages_completes(self, ten_page_pdf: Path, tmp_path: Path) -> None:
        elapsed = _run_fast_pipeline(ten_page_pdf, tmp_path / "out10.md")
        assert elapsed < 120.0, f"10-page PDF took {elapsed:.2f}s (threshold 120s)"


@pytest.mark.slow
class TestPipelineStatistics:
    """Verify that ProcessingStatistics are plausible after a run."""

    def test_statistics_page_count(self, one_page_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.core.config import ConfigManager
        from smart_pdf_scanner.core.pipeline import PipelineBuilder
        from smart_pdf_scanner.models.config import ProcessingMode

        config = ConfigManager.get_preset(ProcessingMode.FAST)
        result = PipelineBuilder(config).build().process(
            one_page_pdf, output_path=tmp_path / "stats.md"
        )
        assert result.statistics is not None
        assert result.statistics.pages_processed >= 1
        assert result.statistics.processing_time_seconds >= 0.0

    def test_statistics_elements_detected(self, one_page_pdf: Path, tmp_path: Path) -> None:
        from smart_pdf_scanner.core.config import ConfigManager
        from smart_pdf_scanner.core.pipeline import PipelineBuilder
        from smart_pdf_scanner.models.config import ProcessingMode

        config = ConfigManager.get_preset(ProcessingMode.FAST)
        result = PipelineBuilder(config).build().process(
            one_page_pdf, output_path=tmp_path / "elem.md"
        )
        assert result.statistics is not None
        assert result.statistics.elements_detected >= 1
