# Project Structure: Smart PDF Scanner

## Overview

Smart PDF Scanner follows a modular, layered architecture that separates core processing logic from interface implementations. The structure supports multiple deployment modes (desktop, CLI, cloud) while maintaining a single source of truth for document processing logic.

## Directory Structure

```
smart-pdf-scanner/
├── src/
│   ├── smart_pdf_scanner/           # Main package
│   │   ├── __init__.py
│   │   ├── core/                    # Core processing engine
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py          # Main processing pipeline
│   │   │   ├── document.py          # Document data models
│   │   │   ├── element.py           # Element base classes
│   │   │   └── config.py            # Configuration management
│   │   │
│   │   ├── stages/                  # Processing stages
│   │   │   ├── __init__.py
│   │   │   ├── pdf_parser.py        # Stage 1: PDF parsing
│   │   │   ├── layout_analyzer.py   # Stage 2: Layout analysis
│   │   │   ├── ocr_processor.py     # Stage 3: OCR processing
│   │   │   ├── structure_recognizer.py  # Stage 4: Structure recognition
│   │   │   ├── table_processor.py   # Stage 5: Table processing
│   │   │   ├── image_processor.py   # Stage 6: Image processing
│   │   │   ├── semantic_enhancer.py # Stage 7: LLM enhancement
│   │   │   └── markdown_generator.py # Stage 8: Markdown generation
│   │   │
│   │   ├── engines/                 # Pluggable engines
│   │   │   ├── __init__.py
│   │   │   ├── ocr/                 # OCR engines
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # OCR engine interface
│   │   │   │   ├── tesseract.py     # Tesseract implementation
│   │   │   │   ├── easyocr.py       # EasyOCR implementation
│   │   │   │   └── cloud_ocr.py     # Cloud OCR (optional)
│   │   │   │
│   │   │   ├── layout/              # Layout detection engines
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # Layout engine interface
│   │   │   │   ├── layoutparser.py  # LayoutParser implementation
│   │   │   │   ├── doctr.py         # DocTR implementation
│   │   │   │   └── heuristic.py     # Rule-based fallback
│   │   │   │
│   │   │   └── llm/                 # LLM providers
│   │   │       ├── __init__.py
│   │   │       ├── base.py          # LLM provider interface
│   │   │       ├── openai.py        # OpenAI implementation
│   │   │       ├── anthropic.py     # Anthropic implementation
│   │   │       └── local.py         # Local model (Ollama)
│   │   │
│   │   ├── models/                  # Data models
│   │   │   ├── __init__.py
│   │   │   ├── document.py          # Document model
│   │   │   ├── page.py              # Page model
│   │   │   ├── elements.py          # Element models (TextBlock, Table, Image)
│   │   │   ├── structure.py         # Structure models (Heading, TOC)
│   │   │   └── metadata.py          # Metadata models
│   │   │
│   │   ├── utils/                   # Utility modules
│   │   │   ├── __init__.py
│   │   │   ├── bbox.py              # Bounding box utilities
│   │   │   ├── image_utils.py       # Image processing utilities
│   │   │   ├── text_utils.py        # Text processing utilities
│   │   │   ├── cache.py             # Caching utilities
│   │   │   └── logging.py           # Logging configuration
│   │   │
│   │   ├── visualization/           # Visualization tools
│   │   │   ├── __init__.py
│   │   │   ├── renderer.py          # Page rendering with bboxes
│   │   │   ├── colors.py            # Color schemes for element types
│   │   │   └── export.py            # Export visualization images
│   │   │
│   │   ├── desktop/                 # Desktop application
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # Application entry point
│   │   │   ├── main_window.py       # Main window
│   │   │   ├── widgets/             # Custom widgets
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf_viewer.py    # PDF viewer widget
│   │   │   │   ├── bbox_overlay.py  # Bounding box overlay
│   │   │   │   ├── structure_tree.py # Structure tree view
│   │   │   │   └── settings_panel.py # Settings panel
│   │   │   └── resources/           # UI resources
│   │   │       ├── icons/
│   │   │       └── styles/
│   │   │
│   │   ├── cli/                     # CLI application
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # CLI entry point
│   │   │   ├── commands/            # CLI commands
│   │   │   │   ├── __init__.py
│   │   │   │   ├── process.py       # Process command
│   │   │   │   ├── batch.py         # Batch processing
│   │   │   │   └── visualize.py     # Visualization command
│   │   │   └── output.py            # Rich output formatting
│   │   │
│   │   └── api/                     # Cloud API
│   │       ├── __init__.py
│   │       ├── main.py              # FastAPI application
│   │       ├── routes/              # API routes
│   │       │   ├── __init__.py
│   │       │   ├── process.py       # Processing endpoints
│   │       │   ├── status.py        # Status endpoints
│   │       │   └── download.py      # Download endpoints
│   │       ├── models/              # API request/response models
│   │       │   ├── __init__.py
│   │       │   ├── requests.py
│   │       │   └── responses.py
│   │       ├── workers/             # Background workers
│   │       │   ├── __init__.py
│   │       │   └── processor.py
│   │       └── storage/             # Storage adapters
│   │           ├── __init__.py
│   │           ├── s3.py
│   │           └── local.py
│   │
│   └── tests/                       # Test suite
│       ├── __init__.py
│       ├── conftest.py              # Pytest configuration
│       ├── fixtures/                # Test fixtures
│       │   ├── pdfs/                # Sample PDFs
│       │   └── expected/            # Expected outputs
│       ├── unit/                    # Unit tests
│       │   ├── test_pipeline.py
│       │   ├── test_stages/
│       │   ├── test_engines/
│       │   └── test_models/
│       ├── integration/             # Integration tests
│       │   ├── test_end_to_end.py
│       │   └── test_api.py
│       └── performance/             # Performance tests
│           └── test_benchmarks.py
│
├── docs/                            # Documentation
│   ├── index.md
│   ├── getting-started.md
│   ├── user-guide/
│   │   ├── desktop-app.md
│   │   ├── cli-usage.md
│   │   └── api-reference.md
│   ├── developer-guide/
│   │   ├── architecture.md
│   │   ├── adding-engines.md
│   │   └── contributing.md
│   └── examples/
│       └── sample-outputs/
│
├── config/                          # Configuration files
│   ├── default.yaml                 # Default configuration
│   ├── fast-mode.yaml               # Fast processing mode
│   ├── balanced-mode.yaml           # Balanced mode
│   └── high-fidelity-mode.yaml      # High fidelity mode
│
├── scripts/                         # Utility scripts
│   ├── setup_models.py              # Download and setup models
│   ├── benchmark.py                 # Benchmarking script
│   └── validate_output.py           # Output validation
│
├── deployment/                      # Deployment configurations
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   └── .dockerignore
│   ├── kubernetes/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   └── cloud/
│       ├── aws/
│       ├── gcp/
│       └── azure/
│
├── .spec-workflow/                  # Spec workflow (current)
│   ├── steering/
│   │   ├── product.md
│   │   ├── tech.md
│   │   └── structure.md
│   └── specs/                       # Future specifications
│
├── requirements/                    # Requirements documents
│   └── smart-pdf-scanner.md
│
├── pyproject.toml                   # Project metadata & dependencies
├── poetry.lock                      # Locked dependencies
├── README.md                        # Project README
├── LICENSE                          # License file
├── .gitignore                       # Git ignore rules
├── .env.example                     # Environment variables template
└── CHANGELOG.md                     # Version changelog
```

## Module Organization

### Core Package (`smart_pdf_scanner/core/`)

**Purpose**: Central processing engine, independent of interface

**Key Files**:
- `pipeline.py`: Orchestrates processing stages, manages data flow
- `document.py`: Document lifecycle management
- `element.py`: Base classes for document elements
- `config.py`: Configuration loading and validation

**Design Principles**:
- No UI dependencies
- Pure Python, testable in isolation
- Interface-agnostic (can be used by desktop, CLI, or API)

### Processing Stages (`smart_pdf_scanner/stages/`)

**Purpose**: Individual processing steps in the pipeline

**Pattern**: Each stage is a class implementing a common interface:

```python
class ProcessingStage(ABC):
    @abstractmethod
    def process(self, document: Document, config: Config) -> Document:
        """Process document and return updated version"""
        pass
    
    @abstractmethod
    def validate(self, document: Document) -> List[ValidationWarning]:
        """Validate stage output"""
        pass
```

**Stage Responsibilities**:
1. **pdf_parser.py**: Extract raw text, images, metadata from PDF
2. **layout_analyzer.py**: Detect layout elements, generate bounding boxes
3. **ocr_processor.py**: OCR for image-based content
4. **structure_recognizer.py**: Build heading hierarchy, reading order
5. **table_processor.py**: Detect and convert tables
6. **image_processor.py**: Classify and describe images
7. **semantic_enhancer.py**: LLM-based refinement (optional)
8. **markdown_generator.py**: Generate final Markdown output

**Dependencies**: Stages can depend on previous stages but not future ones

### Engines (`smart_pdf_scanner/engines/`)

**Purpose**: Pluggable implementations for OCR, layout, and LLM

**Pattern**: Strategy pattern with base interfaces

**Structure**:
- `base.py`: Abstract base class defining interface
- Concrete implementations: `tesseract.py`, `openai.py`, etc.
- Factory pattern for engine selection based on config

**Example Interface**:
```python
class OCREngine(ABC):
    @abstractmethod
    def extract_text(self, image: Image, config: OCRConfig) -> OCRResult:
        pass
    
    @abstractmethod
    def get_confidence(self) -> float:
        pass
```

### Data Models (`smart_pdf_scanner/models/`)

**Purpose**: Pydantic models for type safety and validation

**Key Models**:
- `Document`: Top-level document container
- `Page`: Individual page with elements
- `TextBlock`, `Table`, `Image`: Concrete element types
- `BoundingBox`: Coordinate representation
- `DocumentStructure`: Hierarchical structure

**Benefits**:
- Type validation at runtime
- JSON serialization/deserialization
- IDE autocomplete support
- API schema generation (for FastAPI)

### Utilities (`smart_pdf_scanner/utils/`)

**Purpose**: Shared helper functions

**Modules**:
- `bbox.py`: Bounding box operations (intersection, containment, merging)
- `image_utils.py`: Image preprocessing, format conversion
- `text_utils.py`: Text cleaning, normalization, reading order
- `cache.py`: Result caching (file-based and Redis)
- `logging.py`: Structured logging setup

**Design**: Pure functions where possible, no side effects

### Visualization (`smart_pdf_scanner/visualization/`)

**Purpose**: Render pages with bounding box overlays

**Usage**: Both desktop app and CLI visualization command

**Key Features**:
- Color-coded element types
- Transparency control
- Export to image files
- Annotation support

### Desktop Application (`smart_pdf_scanner/desktop/`)

**Purpose**: PyQt6-based GUI for local use

**Architecture**: MVC pattern
- `main_window.py`: Controller
- `widgets/`: Views
- Core package: Model

**Key Widgets**:
- `pdf_viewer.py`: Displays PDF pages
- `bbox_overlay.py`: Draws bounding boxes on top
- `structure_tree.py`: Shows document hierarchy
- `settings_panel.py`: Configuration UI

### CLI Application (`smart_pdf_scanner/cli/`)

**Purpose**: Command-line interface for automation

**Framework**: Click with Rich for formatting

**Commands**:
- `process`: Process single PDF
- `batch`: Process multiple PDFs
- `visualize`: Generate visualization images
- `config`: Manage configuration

**Example**:
```bash
smart-pdf process input.pdf --mode balanced --output output/
smart-pdf batch pdfs/*.pdf --workers 4 --mode fast
smart-pdf visualize input.pdf --page 1 --output viz.png
```

### Cloud API (`smart_pdf_scanner/api/`)

**Purpose**: FastAPI-based REST API for cloud deployment

**Architecture**: Async request handling with background workers

**Endpoints**:
- `POST /api/v1/process`: Submit processing job
- `GET /api/v1/status/{job_id}`: Check job status
- `GET /api/v1/download/{job_id}`: Download results
- `GET /api/v1/health`: Health check

**Flow**:
1. Client uploads PDF
2. API creates job, stores in database
3. Background worker processes document
4. Client polls status
5. Client downloads results

**Storage**: S3/GCS for PDFs and outputs, PostgreSQL for metadata

## File Naming Conventions

### Python Files
- **Modules**: `snake_case.py` (e.g., `pdf_parser.py`)
- **Classes**: `PascalCase` (e.g., `PDFParser`)
- **Functions**: `snake_case` (e.g., `extract_text`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`)

### Configuration Files
- YAML for configuration: `kebab-case.yaml`
- Environment files: `.env`, `.env.example`

### Documentation
- Markdown files: `kebab-case.md`
- README files: `README.md` (uppercase)

## Import Conventions

### Import Order (per PEP 8)
1. Standard library imports
2. Third-party imports
3. Local application imports

### Example
```python
# Standard library
import os
from pathlib import Path
from typing import List, Optional

# Third-party
import fitz  # PyMuPDF
from pydantic import BaseModel

# Local
from smart_pdf_scanner.core.pipeline import Pipeline
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.utils.logging import get_logger
```

### Absolute vs Relative Imports
- **Preference**: Absolute imports from package root
- **Exception**: Relative imports within same subpackage for closely related modules

## Code Organization Patterns

### Pipeline Pattern
Processing stages are chained in sequence:
```python
pipeline = Pipeline([
    PDFParser(),
    LayoutAnalyzer(),
    OCRProcessor(),
    StructureRecognizer(),
    TableProcessor(),
    ImageProcessor(),
    SemanticEnhancer(),
    MarkdownGenerator()
])

result = pipeline.process(pdf_path, config)
```

### Strategy Pattern
Pluggable engines selected at runtime:
```python
ocr_engine = OCREngineFactory.create(config.ocr_engine)
text = ocr_engine.extract_text(image)
```

### Factory Pattern
Create objects based on configuration:
```python
class OCREngineFactory:
    @staticmethod
    def create(engine_type: str) -> OCREngine:
        if engine_type == "tesseract":
            return TesseractEngine()
        elif engine_type == "easyocr":
            return EasyOCREngine()
        # ...
```

### Builder Pattern
Complex object construction:
```python
document = (DocumentBuilder()
    .with_metadata(metadata)
    .add_page(page1)
    .add_page(page2)
    .build())
```

## Configuration Management

### Configuration Hierarchy
1. **System defaults**: Hardcoded in `config.py`
2. **Config files**: YAML files in `config/`
3. **Environment variables**: `.env` file
4. **CLI arguments**: Override all others

### Configuration Structure
```yaml
# config/default.yaml
processing:
  mode: balanced
  max_file_size_mb: 150
  
ocr:
  engine: tesseract
  languages: [eng]
  confidence_threshold: 0.7
  
layout:
  engine: layoutparser
  model: lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config
  
llm:
  provider: openai
  model: gpt-4-turbo
  max_tokens: 4096
  temperature: 0.1
  
output:
  format: markdown
  include_page_numbers: true
  export_tables_csv: false
```

### Environment Variables
```bash
# .env.example
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

## Testing Structure

### Test Organization
- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test stage interactions and pipeline
- **Performance tests**: Benchmark processing speed and memory

### Test Fixtures
```python
# tests/conftest.py
@pytest.fixture
def sample_pdf():
    return Path("tests/fixtures/pdfs/sample.pdf")

@pytest.fixture
def expected_markdown():
    return Path("tests/fixtures/expected/sample.md").read_text()
```

### Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_<function>_<scenario>()`
- Example: `test_extract_text_multi_column()`

## Logging Strategy

### Log Levels
- **DEBUG**: Detailed processing info, coordinates, confidence scores
- **INFO**: Stage completion, element counts
- **WARNING**: Low confidence, fallback usage
- **ERROR**: Processing failures

### Log Format
```python
# Structured logging
logger.info(
    "Stage completed",
    extra={
        "stage": "layout_analysis",
        "page": 1,
        "elements_detected": 15,
        "processing_time_ms": 234
    }
)
```

### Log Output
- **Console**: INFO and above (with rich formatting)
- **File**: DEBUG and above (JSON format for parsing)
- **Cloud**: Structured logs to CloudWatch/Stackdriver

## Dependency Management

### Core Dependencies
```toml
[tool.poetry.dependencies]
python = "^3.10"
PyMuPDF = "^1.23.0"
pdfplumber = "^0.10.0"
pytesseract = "^0.3.10"
layoutparser = "^0.3.4"
Pillow = "^10.0.0"
pydantic = "^2.0.0"
```

### Optional Dependencies
```toml
[tool.poetry.group.desktop.dependencies]
PyQt6 = "^6.5.0"

[tool.poetry.group.api.dependencies]
fastapi = "^0.109.0"
uvicorn = "^0.27.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
black = "^23.0.0"
ruff = "^0.1.0"
mypy = "^1.7.0"
```

### Installation Profiles
```bash
# Core library only
poetry install

# With desktop app
poetry install --with desktop

# With API server
poetry install --with api

# Development
poetry install --with dev
```

## Build and Distribution

### Package Structure
```
smart-pdf-scanner/
├── src/smart_pdf_scanner/  # Source code
├── pyproject.toml          # Package metadata
└── README.md               # Package description
```

### Entry Points
```toml
[tool.poetry.scripts]
smart-pdf = "smart_pdf_scanner.cli.main:cli"
smart-pdf-desktop = "smart_pdf_scanner.desktop.main:main"
smart-pdf-api = "smart_pdf_scanner.api.main:run"
```

### Distribution
- **PyPI**: `pip install smart-pdf-scanner`
- **Desktop app**: Platform-specific installers (PyInstaller)
- **Docker**: `docker pull smart-pdf-scanner:latest`

## Version Control

### Branch Strategy
- `main`: Production-ready code
- `develop`: Integration branch
- `feature/*`: Feature branches
- `fix/*`: Bug fix branches

### Commit Convention
```
type(scope): subject

body

footer
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(ocr): add EasyOCR engine support

Implement EasyOCR as alternative OCR engine for better
handwriting recognition.

Closes #123
```

## Documentation

### Code Documentation
- **Docstrings**: Google style for all public functions/classes
- **Type hints**: All function signatures
- **Comments**: Explain "why", not "what"

### Example
```python
def extract_text(
    page: fitz.Page,
    bbox: BoundingBox,
    preserve_layout: bool = True
) -> str:
    """Extract text from a specific region of a PDF page.
    
    Args:
        page: PyMuPDF page object
        bbox: Bounding box defining the extraction region
        preserve_layout: If True, maintain spatial layout of text
        
    Returns:
        Extracted text as string
        
    Raises:
        ExtractionError: If text extraction fails
        
    Example:
        >>> page = doc.load_page(0)
        >>> bbox = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        >>> text = extract_text(page, bbox)
    """
    pass
```

### User Documentation
- **Getting Started**: Installation, quick start
- **User Guide**: Desktop app, CLI, API usage
- **Developer Guide**: Architecture, extending, contributing
- **API Reference**: Auto-generated from docstrings

## Performance Considerations

### Memory Management
- Process pages sequentially to limit memory
- Release resources after each page
- Use generators for large document iteration

### Caching Strategy
- **File cache**: OCR results, layout detections
- **Redis cache**: LLM responses (cloud deployment)
- **Cache key**: Hash of input + config

### Parallel Processing
- Multi-page processing in parallel (when memory allows)
- Thread pool for I/O operations
- Process pool for CPU-intensive tasks

## Security Practices

### Input Validation
- File size limits
- File type validation (magic bytes)
- Path traversal prevention

### Secrets Management
- Never commit API keys
- Use environment variables
- Support secret managers (AWS Secrets Manager, etc.)

### Dependency Security
- Regular dependency updates
- Vulnerability scanning (Safety, Snyk)
- Pin versions in production

## Extensibility Points

### Adding New OCR Engine
1. Create class in `engines/ocr/`
2. Inherit from `OCREngine` base class
3. Implement `extract_text()` method
4. Register in factory

### Adding New Processing Stage
1. Create class in `stages/`
2. Inherit from `ProcessingStage`
3. Implement `process()` and `validate()`
4. Add to pipeline configuration

### Adding New Output Format
1. Create generator in `stages/`
2. Implement `generate()` method
3. Register format in config

## Deployment Considerations

### Docker Image Layers
```dockerfile
# Base layer: Python + system dependencies
# Model layer: Pre-downloaded models (cached)
# App layer: Application code (changes frequently)
```

### Environment-Specific Config
- Development: Local files, verbose logging
- Staging: Cloud storage, structured logs
- Production: Optimized settings, monitoring

### Scaling Strategy
- Horizontal: Multiple API instances behind load balancer
- Vertical: Larger instances for memory-intensive documents
- Queue-based: Decouple API from processing workers

## Migration Path

### From Prototype to Production
1. **Phase 1**: Core library with CLI
2. **Phase 2**: Add desktop application
3. **Phase 3**: Add cloud API
4. **Phase 4**: Optimize and scale

### Backward Compatibility
- Semantic versioning
- Deprecation warnings before breaking changes
- Migration guides for major versions
