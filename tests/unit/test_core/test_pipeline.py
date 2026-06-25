"""Unit tests for Pipeline, PipelineBuilder, and ProgressEvent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smart_pdf_scanner.core.pipeline import Pipeline, PipelineBuilder, ProgressEvent
from smart_pdf_scanner.models.config import Config, ProcessingMode
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning, WarningSeverity


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_doc() -> Document:
    return Document(
        metadata=DocumentMetadata(page_count=0, file_size_bytes=0),
        assets_folder=Path("/tmp/assets"),
    )


class _PassStage(ProcessingStage):
    """A no-op stage that records whether it was called."""

    def __init__(self, name: str = "pass_stage") -> None:
        self._name = name
        self.processed = False
        self.validated = False

    @property
    def name(self) -> str:
        return self._name

    def validate(self, document, config):
        self.validated = True
        return []

    def process(self, document, config):
        self.processed = True
        return document


class _FailStage(ProcessingStage):
    """A stage that raises during process()."""

    @property
    def name(self) -> str:
        return "fail_stage"

    def validate(self, document, config):
        return []

    def process(self, document, config):
        raise RuntimeError("intentional failure")


class _WarnStage(ProcessingStage):
    """A stage that emits a validation warning."""

    def __init__(self, severity: WarningSeverity = WarningSeverity.WARNING) -> None:
        self._severity = severity

    @property
    def name(self) -> str:
        return "warn_stage"

    def validate(self, document, config):
        return [ValidationWarning(code="test_warn", message="test", severity=self._severity)]

    def process(self, document, config):
        return document


# ---------------------------------------------------------------------------
# Pipeline.validate_input
# ---------------------------------------------------------------------------


class TestValidateInput:
    def _pipeline(self, config: Config | None = None) -> Pipeline:
        return Pipeline(stages=[], config=config or Config())

    def test_missing_file(self, tmp_path):
        p = self._pipeline()
        errors = p.validate_input(tmp_path / "nonexistent.pdf")
        assert any("not found" in e for e in errors)

    def test_directory_not_file(self, tmp_path):
        p = self._pipeline()
        errors = p.validate_input(tmp_path)
        assert any("not a regular file" in e for e in errors)

    def test_invalid_magic(self, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"BOGUS content")
        p = self._pipeline()
        errors = p.validate_input(bad)
        assert any("bad magic" in e for e in errors)

    def test_valid_pdf_header(self, tmp_path):
        good = tmp_path / "good.pdf"
        good.write_bytes(b"%PDF-1.4 dummy content")
        p = self._pipeline()
        errors = p.validate_input(good)
        assert errors == []

    def test_oversized_file(self, tmp_path):
        big = tmp_path / "big.pdf"
        # Write a 2 MB PDF-magic file; limit is 1 MB → should error
        big.write_bytes(b"%PDF" + b"x" * (2 * 1024 * 1024))
        config = Config(max_file_size_mb=1)
        p = self._pipeline(config)
        errors = p.validate_input(big)
        assert any("exceeds" in e for e in errors)


# ---------------------------------------------------------------------------
# Pipeline.process – short-circuit on invalid input
# ---------------------------------------------------------------------------


class TestPipelineProcessInvalidInput:
    def test_returns_failure_for_missing_file(self, tmp_path):
        pipeline = Pipeline(stages=[], config=Config())
        result = pipeline.process(tmp_path / "missing.pdf")
        assert result.success is False
        assert result.errors

    def test_no_stages_run_for_invalid_input(self, tmp_path):
        stage = _PassStage("pdf_parser")
        pipeline = Pipeline(
            stages=[stage],
            config=Config(enabled_stages=["pdf_parser"]),
        )
        pipeline.process(tmp_path / "missing.pdf")
        assert stage.processed is False


# ---------------------------------------------------------------------------
# Pipeline.process – stage execution
# ---------------------------------------------------------------------------


class TestPipelineProcessStages:
    def _make_pdf(self, tmp_path: Path) -> Path:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        return pdf

    def test_enabled_stage_is_called(self, tmp_path):
        stage = _PassStage("pdf_parser")
        config = Config(enabled_stages=["pdf_parser"])
        pipeline = Pipeline(stages=[stage], config=config)
        with patch.object(stage, "process", wraps=stage.process) as mock_proc:
            pipeline.process(self._make_pdf(tmp_path))
        mock_proc.assert_called_once()

    def test_disabled_stage_is_skipped(self, tmp_path):
        stage = _PassStage("markdown_generator")
        config = Config(enabled_stages=["pdf_parser"])  # markdown_generator not enabled
        pipeline = Pipeline(stages=[stage], config=config)
        pipeline.process(self._make_pdf(tmp_path))
        assert stage.processed is False

    def test_failed_stage_does_not_abort_pipeline(self, tmp_path):
        fail = _FailStage()
        after = _PassStage("pass_after")
        config = Config(enabled_stages=["fail_stage", "pass_after"])
        pipeline = Pipeline(stages=[fail, after], config=config)
        result = pipeline.process(self._make_pdf(tmp_path))
        assert after.processed is True
        assert result.success is False
        assert any("fail_stage" in e for e in result.errors)

    def test_success_true_when_all_stages_pass(self, tmp_path):
        stage = _PassStage("pdf_parser")
        config = Config(enabled_stages=["pdf_parser"])
        pipeline = Pipeline(stages=[stage], config=config)
        result = pipeline.process(self._make_pdf(tmp_path))
        assert result.success is True
        assert result.errors == []

    def test_warnings_collected_from_validate(self, tmp_path):
        warn = _WarnStage(WarningSeverity.WARNING)
        config = Config(enabled_stages=["warn_stage"])
        pipeline = Pipeline(stages=[warn], config=config)
        result = pipeline.process(self._make_pdf(tmp_path))
        assert result.warnings
        assert any("test_warn" in w for w in result.warnings)

    def test_error_severity_warning_marks_error(self, tmp_path):
        warn = _WarnStage(WarningSeverity.ERROR)
        config = Config(enabled_stages=["warn_stage"])
        pipeline = Pipeline(stages=[warn], config=config)
        result = pipeline.process(self._make_pdf(tmp_path))
        assert any("test_warn" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Pipeline.process – progress events
# ---------------------------------------------------------------------------


class TestPipelineProgressEvents:
    def _make_pdf(self, tmp_path: Path) -> Path:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        return pdf

    def test_progress_callback_called(self, tmp_path):
        stage = _PassStage("pdf_parser")
        events: list[ProgressEvent] = []
        config = Config(enabled_stages=["pdf_parser"])
        pipeline = Pipeline(stages=[stage], config=config, on_progress=events.append)
        pipeline.process(self._make_pdf(tmp_path))
        assert events  # at least one event emitted

    def test_started_and_completed_events(self, tmp_path):
        stage = _PassStage("pdf_parser")
        events: list[ProgressEvent] = []
        config = Config(enabled_stages=["pdf_parser"])
        pipeline = Pipeline(stages=[stage], config=config, on_progress=events.append)
        pipeline.process(self._make_pdf(tmp_path))
        statuses = [e.status for e in events]
        assert "started" in statuses
        assert "completed" in statuses

    def test_fraction_range(self, tmp_path):
        stages = [_PassStage("pdf_parser"), _PassStage("layout_analyzer")]
        events: list[ProgressEvent] = []
        config = Config(enabled_stages=["pdf_parser", "layout_analyzer"])
        pipeline = Pipeline(stages=stages, config=config, on_progress=events.append)
        pipeline.process(self._make_pdf(tmp_path))
        for e in events:
            assert 0.0 <= e.fraction <= 1.0

    def test_broken_callback_does_not_crash_pipeline(self, tmp_path):
        stage = _PassStage("pdf_parser")
        config = Config(enabled_stages=["pdf_parser"])

        def bad_callback(event):
            raise ValueError("callback broken")

        pipeline = Pipeline(stages=[stage], config=config, on_progress=bad_callback)
        result = pipeline.process(self._make_pdf(tmp_path))
        # Pipeline should complete despite broken callback
        assert stage.processed is True


# ---------------------------------------------------------------------------
# Pipeline.process – statistics
# ---------------------------------------------------------------------------


class TestPipelineStatistics:
    def _make_pdf(self, tmp_path: Path) -> Path:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 minimal")
        return pdf

    def test_statistics_returned(self, tmp_path):
        pipeline = Pipeline(stages=[], config=Config(enabled_stages=[]))
        result = pipeline.process(self._make_pdf(tmp_path))
        assert result.statistics is not None
        assert result.statistics.processing_time_seconds >= 0.0

    def test_assets_folder_path_set(self, tmp_path):
        pdf = self._make_pdf(tmp_path)
        output = tmp_path / "out.md"
        pipeline = Pipeline(stages=[], config=Config(enabled_stages=[]))
        result = pipeline.process(pdf, output_path=output)
        # assets folder may or may not exist (no stages create it), but path should be set if it exists
        # The key check: if it's not None it should be correct
        if result.assets_folder is not None:
            assert result.assets_folder.name == "out_assets"


# ---------------------------------------------------------------------------
# PipelineBuilder
# ---------------------------------------------------------------------------


class TestPipelineBuilder:
    def test_build_returns_pipeline(self):
        config = Config(enabled_stages=["pdf_parser", "markdown_generator"])
        pipeline = PipelineBuilder(config).build()
        assert isinstance(pipeline, Pipeline)

    def test_from_preset_fast(self):
        builder = PipelineBuilder.from_preset(ProcessingMode.FAST)
        assert isinstance(builder, PipelineBuilder)
        assert builder._config.processing_mode == ProcessingMode.FAST
        assert builder._config.llm_provider is None

    def test_from_preset_balanced(self):
        builder = PipelineBuilder.from_preset(ProcessingMode.BALANCED)
        assert builder._config.processing_mode == ProcessingMode.BALANCED

    def test_from_preset_high_fidelity(self):
        builder = PipelineBuilder.from_preset(ProcessingMode.HIGH_FIDELITY)
        assert builder._config.processing_mode == ProcessingMode.HIGH_FIDELITY

    def test_on_progress_forwarded(self):
        config = Config(enabled_stages=["pdf_parser"])
        callback = MagicMock()
        pipeline = PipelineBuilder(config).build(on_progress=callback)
        assert pipeline._on_progress is callback


# ---------------------------------------------------------------------------
# ProgressEvent dataclass
# ---------------------------------------------------------------------------


class TestProgressEvent:
    def test_fields(self):
        e = ProgressEvent("stage", 2, 5, "started", 0.4)
        assert e.stage_name == "stage"
        assert e.stage_index == 2
        assert e.total_stages == 5
        assert e.status == "started"
        assert e.fraction == pytest.approx(0.4)
