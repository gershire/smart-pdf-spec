# Smart PDF Scanner

Intelligent PDF-to-Markdown converter with structural fidelity.

## Overview

Smart PDF Scanner converts PDF documents into structured, machine-readable Markdown while preserving semantic structure, visual organization, and element relationships. It handles complex layouts, multi-column documents, scanned images, and hybrid PDFs through a pluggable processing pipeline.

## Features

- **Structural fidelity** — headings, reading order, and section hierarchy preserved
- **Complex layout handling** — multi-column, tables, images, captions, footnotes
- **Intelligent OCR** — Tesseract and EasyOCR with automatic confidence-based fallback
- **Table extraction** — Markdown output with optional CSV export via pdfplumber
- **Image processing** — visual classification, embedded-text OCR, LLM-generated descriptions
- **Semantic enhancement** — LLM-powered summary, keyword, and entity extraction
- **Three processing modes** — Fast, Balanced, High-Fidelity (see below)
- **Fully configurable** — YAML files, environment variables, or Python API

## Installation

```bash
# Clone and install
git clone https://github.com/gershire/smart-pdf-spec.git
cd smart-pdf-spec
pip install -e ".[dev]"          # or: poetry install --with dev

# Tesseract OCR (required for scanned PDFs)
# macOS:   brew install tesseract
# Ubuntu:  sudo apt install tesseract-ocr
```

## Quick Start

### Command line

```bash
# Process with default (balanced) settings
python -m smart_pdf_scanner document.pdf

# Choose a mode
python -m smart_pdf_scanner document.pdf --mode fast
python -m smart_pdf_scanner document.pdf --mode high_fidelity

# Specify output path and config file
python -m smart_pdf_scanner document.pdf -o output.md -c config/fast-mode.yaml

# Options
python -m smart_pdf_scanner --help
```

### Python API

```python
from pathlib import Path
from smart_pdf_scanner.core.config import ConfigManager
from smart_pdf_scanner.core.pipeline import PipelineBuilder
from smart_pdf_scanner.models.config import ProcessingMode

# Quick run with a preset
config = ConfigManager.get_preset(ProcessingMode.FAST)
pipeline = PipelineBuilder(config).build()
result = pipeline.process(Path("document.pdf"), output_path=Path("output.md"))

print(result.success)                          # True
print(result.statistics.pages_processed)       # e.g. 12
print(result.markdown_path)                    # Path("output.md")

# Load from a YAML config file
config = ConfigManager.load("config/high-fidelity-mode.yaml")
result = PipelineBuilder(config).build().process(Path("report.pdf"))
```

## Processing Modes

| Mode | Speed | Stages | LLM | Use case |
|------|-------|--------|-----|----------|
| **fast** | ~1–2 s/page | pdf_parser, layout_analyzer, ocr_processor, table_processor, markdown_generator | No | Batch conversion, CI pipelines |
| **balanced** | ~3–5 s/page | All stages | No | General-purpose conversion |
| **high_fidelity** | ~10–15 s/page | All stages | Yes (OpenAI / Anthropic) | Research, archival, maximum accuracy |

Config files for each mode live in `config/`.

## Configuration

Configuration sources are merged in this order (later overrides earlier):

```
defaults → YAML file → environment variables → explicit overrides
```

### YAML file

```bash
# Edit a preset or copy the default
cp config/balanced-mode.yaml config/my-config.yaml
python -m smart_pdf_scanner doc.pdf -c config/my-config.yaml
```

Key YAML sections:

```yaml
processing:
  mode: balanced          # fast | balanced | high_fidelity
  parallel_pages: false

ocr:
  engine: tesseract       # tesseract | easyocr
  confidence_threshold: 0.7

layout:
  engine: heuristic       # heuristic | layoutparser
  confidence_threshold: 0.7

llm:
  provider: openai        # openai | anthropic | null
  model: gpt-4-turbo
```

See `config/default.yaml` for all options with documentation.

### Environment variables

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
# Set API keys for LLM/semantic enhancement
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Override any Config field with SMART_PDF_ prefix
SMART_PDF_PROCESSING_MODE=fast
SMART_PDF_LOG_LEVEL=DEBUG
```

## Project Structure

```
smart-pdf-scanner/
├── src/smart_pdf_scanner/
│   ├── __main__.py          # python -m smart_pdf_scanner entry point
│   ├── core/
│   │   ├── pipeline.py      # Pipeline, PipelineBuilder
│   │   └── config.py        # ConfigManager (YAML + env loading)
│   ├── stages/              # Processing stages (one per concern)
│   │   ├── pdf_parser.py
│   │   ├── layout_analyzer.py
│   │   ├── ocr_processor.py
│   │   ├── structure_recognizer.py
│   │   ├── table_processor.py
│   │   ├── image_processor.py
│   │   ├── semantic_enhancer.py
│   │   └── markdown_generator.py
│   ├── engines/             # Pluggable OCR / layout / LLM engines
│   │   ├── ocr/             # Tesseract, EasyOCR
│   │   ├── layout/          # Heuristic, LayoutParser
│   │   └── llm/             # OpenAI, Anthropic
│   ├── models/              # Pydantic data models
│   ├── utils/               # Bbox, text, image utilities
│   └── visualization/       # Layout / element colour rendering
├── config/                  # YAML configuration presets
│   ├── default.yaml
│   ├── fast-mode.yaml
│   ├── balanced-mode.yaml
│   └── high-fidelity-mode.yaml
├── tests/
│   ├── unit/                # Stage, engine, model, utility unit tests
│   ├── integration/         # End-to-end pipeline tests
│   └── performance/         # Throughput benchmarks
└── pyproject.toml
```

## Extending the Pipeline

### Add a custom stage

```python
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning
from smart_pdf_scanner.models.config import Config
from smart_pdf_scanner.models.document import Document

class MyStage(ProcessingStage):
    @property
    def name(self) -> str:
        return "my_stage"

    def validate(self, document: Document, config: Config) -> list[ValidationWarning]:
        return []  # add pre-condition checks here

    def process(self, document: Document, config: Config) -> Document:
        for page in document.pages:
            for element in page.elements:
                pass  # transform elements here
        return document
```

Register it in `config.enabled_stages` and pass it to `Pipeline(stages=[..., MyStage()])`.

### Add a custom OCR engine

Subclass `smart_pdf_scanner.engines.ocr.base.OCREngine`, implement `extract_text()`, and pass an instance to `OCRProcessor(primary_engine=MyEngine())`.

## Development

```bash
# Install dev dependencies
poetry install --with dev

# Run tests (fast — excludes slow performance benchmarks)
pytest -m "not slow"

# Run linting
ruff check src/

# Type checking
mypy src/smart_pdf_scanner/

# Format
black src/ tests/
```

## Requirements

- Python 3.10+
- `PyMuPDF` (PDF parsing)
- `Pillow` (image handling)
- `pytesseract` + Tesseract binary (OCR)
- `pdfplumber` (table extraction)
- `openai` or `anthropic` SDK (optional, high-fidelity mode only)

## License

MIT

## Acknowledgments

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF parsing
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — OCR engine
- [LayoutParser](https://github.com/Layout-Parser/layout-parser) — layout detection
- [pdfplumber](https://github.com/jsvine/pdfplumber) — table extraction
- [Pydantic](https://github.com/pydantic/pydantic) — data validation
