"""Smart PDF Scanner - Intelligent PDF to Markdown converter with structural fidelity."""

__version__ = "0.1.0"
__author__ = "Smart PDF Scanner Team"

from smart_pdf_scanner.core.pipeline import Pipeline
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.config import Config, ProcessingMode

__all__ = [
    "Pipeline",
    "Document",
    "Config",
    "ProcessingMode",
    "__version__",
]
