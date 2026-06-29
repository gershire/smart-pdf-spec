"""Command-line entry point for the Smart PDF Scanner pipeline.

Usage::

    python -m smart_pdf_scanner input.pdf [options]

or, after ``pip install``::

    smart-pdf-run input.pdf [options]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smart-pdf-scanner",
        description="Convert a PDF to structured Markdown with Smart PDF Scanner.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file.")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Output Markdown file path (default: <pdf_stem>.md alongside the input).",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to a YAML configuration file (e.g. config/fast-mode.yaml).",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "balanced", "high_fidelity"],
        default=None,
        help="Processing mode preset; overridden by --config if both are given.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        metavar="LEVEL",
        help="Logging level (default: INFO).",
    )
    parser.add_argument(
        "--no-page-numbers",
        action="store_true",
        help="Omit page-number dividers from the Markdown output.",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export extracted tables as CSV files alongside the Markdown.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version()}",
    )
    return parser


def _version() -> str:
    try:
        from smart_pdf_scanner import __version__
        return __version__
    except ImportError:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns an exit code (0 = success)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level = args.log_level or "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("smart_pdf_scanner.cli")

    # ── Config ───────────────────────────────────────────────────────────────
    from smart_pdf_scanner.core.config import ConfigManager
    from smart_pdf_scanner.models.config import ProcessingMode

    overrides: dict = {}
    if args.no_page_numbers:
        overrides["include_page_numbers"] = False
    if args.export_csv:
        overrides["export_tables_csv"] = True
    if args.log_level:
        overrides["log_level"] = args.log_level

    if args.config:
        try:
            config = ConfigManager.load(config_path=args.config, overrides=overrides)
        except FileNotFoundError as exc:
            logger.error("Config file not found: %s", exc)
            return 1
        except Exception as exc:
            logger.error("Failed to load config: %s", exc)
            return 1
    elif args.mode:
        mode = ProcessingMode(args.mode)
        config = ConfigManager.get_preset(mode)
        if overrides:
            config = config.model_copy(update=overrides)
    else:
        config = ConfigManager.load(overrides=overrides)

    errors = ConfigManager.validate(config)
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        return 1

    # ── Input validation ─────────────────────────────────────────────────────
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.exists():
        logger.error("PDF file not found: %s", pdf_path)
        return 1

    output_path: Path | None = args.output
    if output_path is None:
        output_path = pdf_path.parent / (pdf_path.stem + ".md")

    # ── Build and run pipeline ───────────────────────────────────────────────
    from smart_pdf_scanner.core.pipeline import PipelineBuilder

    logger.info("Processing %s → %s", pdf_path, output_path)
    logger.info("Mode: %s", config.processing_mode.value)

    try:
        pipeline = PipelineBuilder(config).build()
        result = pipeline.process(pdf_path, output_path=output_path)
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        return 1

    # ── Report ───────────────────────────────────────────────────────────────
    if result.warnings:
        for w in result.warnings:
            logger.warning(w)

    if result.errors:
        for e in result.errors:
            logger.error(e)

    stats = result.statistics
    if stats:
        logger.info(
            "Done: %d pages, %d elements, %.2fs",
            stats.pages_processed,
            stats.elements_detected,
            stats.processing_time_seconds,
        )

    if result.success:
        print(str(output_path))
        return 0
    else:
        logger.error("Processing completed with errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
