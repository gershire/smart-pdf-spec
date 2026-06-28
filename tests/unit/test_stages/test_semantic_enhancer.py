"""Unit tests for SemanticEnhancer stage (task 7.4)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from smart_pdf_scanner.models.config import Config, LLMConfig
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import BoundingBox, ElementType, Heading, Image, ImageType
from smart_pdf_scanner.models.metadata import DocumentMetadata
from smart_pdf_scanner.models.page import Page, PageDimensions
from smart_pdf_scanner.models.structure import DocumentStructure, TableOfContents
from smart_pdf_scanner.stages.base import ValidationWarning
from smart_pdf_scanner.stages.semantic_enhancer import SemanticEnhancer


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_cfg() -> LLMConfig:
    return LLMConfig(provider="openai", model="gpt-4", max_tokens=256, temperature=0.0)


def _make_doc(headings=None, image_elements=None, caption_elements=None) -> Document:
    page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
    if image_elements:
        for el in image_elements:
            page.add_element(el)
    if caption_elements:
        for el in caption_elements:
            page.add_element(el)
    doc = Document(
        metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
        assets_folder=Path("/tmp"),
    )
    doc.add_page(page)
    if headings:
        doc.structure = DocumentStructure(
            headings=headings,
            toc=TableOfContents(entries=[]),
            reading_order=[],
        )
    return doc


def _heading(text: str, level: int = 2, confidence: float = 0.5) -> Heading:
    return Heading(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.HEADING,
        bbox=BoundingBox(x0=50, y0=50, x1=400, y1=70),
        page_number=0,
        text=text,
        level=level,
        confidence=confidence,
    )


def _image_el() -> Image:
    img = Image(
        element_id=str(uuid.uuid4()),
        element_type=ElementType.IMAGE,
        bbox=BoundingBox(x0=50, y0=100, x1=300, y1=250),
        page_number=0,
        image_type=ImageType.PHOTO,
    )
    return img


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSemanticEnhancerName:
    def test_name(self) -> None:
        assert SemanticEnhancer().name == "semantic_enhancer"


class TestSemanticEnhancerValidate:
    def test_no_llm_with_config_emits_warning(self) -> None:
        doc = _make_doc()
        config = Config(llm_provider="openai")
        warnings = SemanticEnhancer(llm_provider=None).validate(doc, config)
        assert any(w.code == "no_llm_provider" for w in warnings)

    def test_no_warning_when_provider_supplied(self) -> None:
        doc = _make_doc()
        mock_llm = MagicMock()
        warnings = SemanticEnhancer(llm_provider=mock_llm).validate(doc, Config())
        assert warnings == []

    def test_no_warning_when_no_provider_configured(self) -> None:
        doc = _make_doc()
        config = Config(llm_provider=None)
        warnings = SemanticEnhancer(llm_provider=None).validate(doc, config)
        assert warnings == []


class TestSemanticEnhancerProcess:
    def test_no_op_when_no_llm(self) -> None:
        heading = _heading("Test", confidence=0.4)
        doc = _make_doc(headings=[heading])
        original_level = heading.level
        SemanticEnhancer(llm_provider=None).process(doc, Config())
        assert heading.level == original_level

    def test_process_calls_refine_and_enhance(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "[]"
        enhancer = SemanticEnhancer(llm_provider=mock_llm)
        heading = _heading("Ambiguous", confidence=0.4)
        doc = _make_doc(headings=[heading])
        enhancer.process(doc, Config(llm_provider="openai"))
        assert mock_llm.generate_text.called


class TestRefineHierarchy:
    def test_refines_ambiguous_headings(self, llm_cfg: LLMConfig) -> None:
        h1 = _heading("Intro", level=3, confidence=0.4)  # ambiguous (low conf)
        h2 = _heading("Conclusion", level=3, confidence=0.9)  # not ambiguous
        doc = _make_doc(headings=[h1, h2])
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps([1])  # LLM says H1
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        assert h1.level == 1  # updated by LLM

    def test_skips_when_no_ambiguous_headings(self, llm_cfg: LLMConfig) -> None:
        h = _heading("High confidence", confidence=0.95)
        doc = _make_doc(headings=[h])
        mock_llm = MagicMock()
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        assert not mock_llm.generate_text.called

    def test_skips_when_no_structure(self, llm_cfg: LLMConfig) -> None:
        doc = _make_doc()  # no structure set
        mock_llm = MagicMock()
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        assert not mock_llm.generate_text.called

    def test_ignores_invalid_llm_response(self, llm_cfg: LLMConfig) -> None:
        h = _heading("Test", level=2, confidence=0.3)
        doc = _make_doc(headings=[h])
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "not valid json"
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        assert h.level == 2  # unchanged

    def test_ignores_mismatched_levels_count(self, llm_cfg: LLMConfig) -> None:
        h1 = _heading("A", confidence=0.3)
        h2 = _heading("B", confidence=0.3)
        doc = _make_doc(headings=[h1, h2])
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps([1])  # only 1 item but 2 headings
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        # Should not apply partial updates
        assert h1.level == 2  # unchanged

    def test_level_out_of_range_not_applied(self, llm_cfg: LLMConfig) -> None:
        h = _heading("Test", level=2, confidence=0.3)
        doc = _make_doc(headings=[h])
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = json.dumps([99])  # invalid level
        SemanticEnhancer(llm_provider=mock_llm).refine_hierarchy(doc, llm_cfg)
        assert h.level == 2  # unchanged


class TestResolveAmbiguities:
    def test_caption_reclassified_as_heading(self, llm_cfg: LLMConfig) -> None:
        from smart_pdf_scanner.models.elements import TextBlock, FontInfo
        caption_el = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.CAPTION,
            bbox=BoundingBox(x0=50, y0=50, x1=300, y1=70),
            page_number=0,
            text="Section Title",
        )
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        page.add_element(caption_el)
        doc = Document(
            metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
            assets_folder=Path("/tmp"),
        )
        doc.add_page(page)
        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "heading"
        SemanticEnhancer(llm_provider=mock_llm).resolve_ambiguities(doc, llm_cfg)
        assert caption_el.element_type == ElementType.HEADING

    def test_long_captions_not_queried(self, llm_cfg: LLMConfig) -> None:
        from smart_pdf_scanner.models.elements import TextBlock
        long_caption = TextBlock(
            element_id=str(uuid.uuid4()),
            element_type=ElementType.CAPTION,
            bbox=BoundingBox(x0=50, y0=50, x1=400, y1=200),
            page_number=0,
            text="x" * 300,  # > 200 chars → skip
        )
        page = Page(page_number=0, dimensions=PageDimensions(width=595.0, height=842.0))
        page.add_element(long_caption)
        doc = Document(
            metadata=DocumentMetadata(page_count=1, file_size_bytes=0),
            assets_folder=Path("/tmp"),
        )
        doc.add_page(page)
        mock_llm = MagicMock()
        SemanticEnhancer(llm_provider=mock_llm).resolve_ambiguities(doc, llm_cfg)
        assert not mock_llm.generate_text.called
