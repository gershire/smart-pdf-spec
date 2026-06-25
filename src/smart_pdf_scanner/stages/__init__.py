"""Processing stages package.

Public surface for all pipeline stages:

- :class:`~smart_pdf_scanner.stages.base.ProcessingStage` — abstract interface
- :class:`~smart_pdf_scanner.stages.base.ValidationWarning` — warning model
- :class:`~smart_pdf_scanner.stages.pdf_parser.PDFParser` — raw PDF extraction
- :class:`~smart_pdf_scanner.stages.layout_analyzer.LayoutAnalyzer` — layout detection
- :class:`~smart_pdf_scanner.stages.ocr_processor.OCRProcessor` — OCR processing
- :class:`~smart_pdf_scanner.stages.structure_recognizer.StructureRecognizer` — structure analysis
- :class:`~smart_pdf_scanner.stages.table_processor.TableProcessor` — table extraction
- :class:`~smart_pdf_scanner.stages.image_processor.ImageProcessor` — image processing
- :class:`~smart_pdf_scanner.stages.semantic_enhancer.SemanticEnhancer` — LLM enhancement
- :class:`~smart_pdf_scanner.stages.markdown_generator.MarkdownGenerator` — Markdown output
"""

from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning, WarningSeverity
from smart_pdf_scanner.stages.image_processor import ImageProcessor
from smart_pdf_scanner.stages.layout_analyzer import LayoutAnalyzer
from smart_pdf_scanner.stages.markdown_generator import MarkdownGenerator
from smart_pdf_scanner.stages.ocr_processor import OCRProcessor
from smart_pdf_scanner.stages.pdf_parser import PDFParser
from smart_pdf_scanner.stages.semantic_enhancer import SemanticEnhancer
from smart_pdf_scanner.stages.structure_recognizer import StructureRecognizer
from smart_pdf_scanner.stages.table_processor import TableProcessor

__all__ = [
    "ProcessingStage",
    "ValidationWarning",
    "WarningSeverity",
    "PDFParser",
    "LayoutAnalyzer",
    "OCRProcessor",
    "StructureRecognizer",
    "TableProcessor",
    "ImageProcessor",
    "SemanticEnhancer",
    "MarkdownGenerator",
]
