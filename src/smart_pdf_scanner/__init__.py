"""Smart PDF Scanner - Intelligent PDF to Markdown converter with structural fidelity."""

__version__ = "0.1.0"
__author__ = "Smart PDF Scanner Team"

from smart_pdf_scanner.core.pipeline import Pipeline, PipelineBuilder
from smart_pdf_scanner.models.config import Config, ProcessingMode
from smart_pdf_scanner.models.document import Document

__all__ = [
    "Config",
    "Document",
    "Pipeline",
    "PipelineBuilder",
    "ProcessingMode",
    "__version__",
]
