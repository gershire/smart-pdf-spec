# Smart PDF Scanner

Intelligent PDF to Markdown converter with structural fidelity.

## Overview

Smart PDF Scanner converts PDF documents into structured, machine-readable Markdown format while preserving semantic structure, visual organization, and element relationships. The system handles complex layouts, multi-column documents, scanned images, and hybrid PDFs with a focus on structural and semantic fidelity.

## Features

- **Structural Fidelity**: Preserves document hierarchy, reading order, and relationships
- **Complex Layout Handling**: Multi-column layouts, tables, images, footnotes
- **Intelligent OCR**: Tesseract and EasyOCR with automatic fallback
- **Table Processing**: Converts tables to Markdown with structure preservation
- **Image Processing**: Classification, OCR, and AI-generated descriptions
- **Multiple Deployment Modes**: Desktop app, CLI tool, Cloud API
- **Configurable Processing**: Fast, balanced, and high-fidelity modes

## Installation

### Using Poetry (Recommended)

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/yourusername/smart-pdf-scanner.git
cd smart-pdf-scanner

# Install dependencies
poetry install

# For desktop app
poetry install --with desktop

# For CLI tool
poetry install --with cli

# For API server
poetry install --with api

# For development
poetry install --with dev
```

### Using pip

```bash
pip install smart-pdf-scanner
```

## Quick Start

### Python API

```python
from smart_pdf_scanner import Pipeline, Config

# Create pipeline with default config
pipeline = Pipeline.from_config(Config())

# Process a PDF
result = pipeline.process("document.pdf")

# Access the markdown output
print(result.markdown_path)
```

### Command Line

```bash
# Process a single PDF
smart-pdf process input.pdf --output output/

# Batch process multiple PDFs
smart-pdf batch pdfs/*.pdf --mode fast

# Visualize layout detection
smart-pdf visualize input.pdf --page 1 --output viz.png
```

## Configuration

Configuration can be provided via:
1. YAML file (`config/default.yaml`)
2. Environment variables
3. Command-line arguments

See `config/default.yaml` for all available options.

## Processing Modes

- **Fast**: Basic text extraction and layout analysis (1-2 sec/page)
- **Balanced**: Full processing with OCR and structure recognition (3-5 sec/page)
- **High-Fidelity**: Maximum accuracy with LLM enhancement (10-15 sec/page)

## Requirements

- Python 3.10+
- Tesseract OCR (for OCR processing)
- 16GB RAM recommended
- GPU optional (improves performance)

## Documentation

- [User Guide](docs/user-guide/)
- [Developer Guide](docs/developer-guide/)
- [API Reference](docs/api-reference/)

## Project Structure

```
smart-pdf-scanner/
├── src/smart_pdf_scanner/    # Main package
│   ├── core/                 # Core pipeline
│   ├── stages/               # Processing stages
│   ├── engines/              # Pluggable engines (OCR, layout, LLM)
│   ├── models/               # Data models
│   ├── utils/                # Utilities
│   ├── visualization/        # Visualization tools
│   ├── desktop/              # Desktop application
│   ├── cli/                  # CLI application
│   └── api/                  # Cloud API
├── tests/                    # Test suite
├── docs/                     # Documentation
├── config/                   # Configuration files
└── pyproject.toml            # Project metadata
```

## Development

```bash
# Install development dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Run linting
poetry run ruff check .

# Format code
poetry run black .

# Type checking
poetry run mypy src/
```

## License

[Your License Here]

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

Built with:
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF processing
- [Tesseract](https://github.com/tesseract-ocr/tesseract) - OCR
- [LayoutParser](https://github.com/Layout-Parser/layout-parser) - Layout analysis
- [Pydantic](https://github.com/pydantic/pydantic) - Data validation
