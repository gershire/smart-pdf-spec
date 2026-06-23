"""Smart PDF Scanner - Intelligent PDF to Markdown converter with structural fidelity."""

__version__ = "0.1.0"
__author__ = "Smart PDF Scanner Team"

from smart_pdf_scanner.models.config import Config, ProcessingMode
from smart_pdf_scanner.models.document import Document

# Re-exported once its implementing task lands:
#   from smart_pdf_scanner.core.pipeline import Pipeline

__all__ = [
    "Config",
    "Document",
    "ProcessingMode",
    "__version__",
]
