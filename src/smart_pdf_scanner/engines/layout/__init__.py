"""Layout engine package.

Public surface for the layout engine layer:

- :class:`~smart_pdf_scanner.engines.layout.base.LayoutEngine` — abstract interface
- :class:`~smart_pdf_scanner.engines.layout.heuristic.HeuristicEngine` — fallback engine
- :class:`~smart_pdf_scanner.engines.layout.layoutparser.LayoutParserEngine` — primary engine
"""

from smart_pdf_scanner.engines.layout.base import LayoutEngine
from smart_pdf_scanner.engines.layout.heuristic import HeuristicEngine
from smart_pdf_scanner.engines.layout.layoutparser import LayoutParserEngine

__all__ = ["LayoutEngine", "HeuristicEngine", "LayoutParserEngine"]
