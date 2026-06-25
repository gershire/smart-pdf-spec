"""OCR engine package.

Public surface for the OCR engine layer:

- :class:`~smart_pdf_scanner.engines.ocr.base.OCREngine` — abstract interface
- :class:`~smart_pdf_scanner.engines.ocr.base.OCRResult` — result model
- :class:`~smart_pdf_scanner.engines.ocr.base.OCRWord` — per-word token model
- :class:`~smart_pdf_scanner.engines.ocr.tesseract.TesseractEngine` — primary engine
- :class:`~smart_pdf_scanner.engines.ocr.easyocr.EasyOCREngine` — fallback engine
"""

from smart_pdf_scanner.engines.ocr.base import OCREngine, OCRResult, OCRWord
from smart_pdf_scanner.engines.ocr.easyocr import EasyOCREngine
from smart_pdf_scanner.engines.ocr.tesseract import TesseractEngine

__all__ = ["OCREngine", "OCRResult", "OCRWord", "TesseractEngine", "EasyOCREngine"]
