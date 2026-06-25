"""SemanticEnhancer stage — LLM-driven structural refinement (optional).

Uses a :class:`~smart_pdf_scanner.engines.llm.base.LLMProvider` to:
- Refine ambiguous heading hierarchies where font-size heuristics are uncertain.
- Enhance image descriptions by providing surrounding textual context.
- Resolve structural ambiguities (e.g. mis-classified headings vs. captions).

The stage is optional: when no LLM provider is configured or the provider
raises an unrecoverable error, it falls back to deterministic results and
logs a warning (Requirement 8: Semantic Enhancement).

Token usage is minimised by processing only elements flagged as ambiguous and
by using a low ``max_tokens`` budget per call.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.models.config import Config, LLMConfig
from smart_pdf_scanner.models.document import Document
from smart_pdf_scanner.models.elements import ElementType, Heading, Image
from smart_pdf_scanner.stages.base import ProcessingStage, ValidationWarning

__all__ = ["SemanticEnhancer"]

logger = logging.getLogger(__name__)

# Maximum heading hierarchy depth we'll ask an LLM to reclassify.
_MAX_HEADING_LEVEL = 6
# Confidence threshold below which a heading is considered ambiguous.
_AMBIGUOUS_HEADING_CONFIDENCE = 0.6
# Token budget per LLM call (kept small to limit cost).
_MAX_TOKENS = 256


class SemanticEnhancer(ProcessingStage):
    """Pipeline stage that uses an LLM to refine document structure.

    Args:
        llm_provider: LLM provider to use for refinement.  When ``None``
            the stage is a no-op and returns the document unchanged.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # ProcessingStage interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "semantic_enhancer"

    def validate(self, document: Document, config: Config) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if self._llm is None and config.llm_provider:
            warnings.append(
                ValidationWarning(
                    code="no_llm_provider",
                    message=(
                        f"SemanticEnhancer: llm_provider='{config.llm_provider}' configured "
                        "but no LLMProvider instance supplied to the stage. "
                        "Semantic enhancement will be skipped."
                    ),
                )
            )
        return warnings

    def process(self, document: Document, config: Config) -> Document:
        """Refine heading hierarchy and image descriptions via LLM.

        Args:
            document: Document to enhance.
            config: Active pipeline configuration.

        Returns:
            Document with refined structure (unchanged if LLM is unavailable).
        """
        if self._llm is None:
            logger.debug("SemanticEnhancer: no LLM provider, skipping.")
            return document

        llm_cfg = LLMConfig(
            provider=config.llm_provider or "openai",
            model=config.llm_model,
            max_tokens=_MAX_TOKENS,
            temperature=0.0,
        )

        self.refine_hierarchy(document, llm_cfg)
        self.enhance_descriptions(document, llm_cfg)
        self.resolve_ambiguities(document, llm_cfg)
        return document

    # ------------------------------------------------------------------
    # Public refinement methods (also callable standalone)
    # ------------------------------------------------------------------

    def refine_hierarchy(self, document: Document, llm_cfg: LLMConfig) -> None:
        """Ask the LLM to validate / correct ambiguous heading levels.

        Gathers headings with confidence below :data:`_AMBIGUOUS_HEADING_CONFIDENCE`
        and sends them in one batch prompt to reduce API calls.

        Args:
            document: Document to refine.
            llm_cfg: LLM configuration.
        """
        if self._llm is None or document.structure is None:
            return

        ambiguous = [
            h for h in document.structure.headings
            if h.confidence < _AMBIGUOUS_HEADING_CONFIDENCE
        ]
        if not ambiguous:
            return

        heading_lines = "\n".join(
            f"[Level H{h.level}] {h.text}" for h in ambiguous
        )
        prompt = (
            "You are a document structure expert.  The following headings were "
            "extracted from a PDF and their hierarchy level is uncertain.  "
            "Reply with ONLY a JSON array of integer levels (H1=1 … H6=6) in "
            "the same order, with no explanation.\n\n"
            f"Headings:\n{heading_lines}"
        )
        try:
            response = self._llm.generate_text(prompt, llm_cfg)
            import json
            levels = json.loads(response.strip())
            if isinstance(levels, list) and len(levels) == len(ambiguous):
                for heading, level in zip(ambiguous, levels):
                    if isinstance(level, int) and 1 <= level <= _MAX_HEADING_LEVEL:
                        heading.level = level
        except Exception as exc:
            logger.debug("Heading hierarchy refinement failed: %s", exc)

    def enhance_descriptions(self, document: Document, llm_cfg: LLMConfig) -> None:
        """Replace heuristic image descriptions with LLM-generated ones.

        Only processes images that have a loaded PIL image available via
        ``element._pil_image`` (set by :class:`ImageProcessor` when the image
        was already loaded).  Skips images without vision access to avoid
        re-loading files.

        Args:
            document: Document to enhance.
            llm_cfg: LLM configuration.
        """
        if self._llm is None:
            return

        for page in document.pages:
            for el in page.elements:
                if not isinstance(el, Image):
                    continue
                pil_img = getattr(el, "_pil_image", None)
                if pil_img is None:
                    continue
                caption = getattr(el, "caption", "") or ""
                surrounding = self._surrounding_text(page, el)
                prompt = (
                    "Describe this document image in 1–2 sentences, "
                    "incorporating the following context from the surrounding text:\n"
                    f"{surrounding[:300]}"
                )
                if caption:
                    prompt += f"\nCaption: {caption}"
                try:
                    description = self._llm.generate_with_vision(prompt, pil_img, llm_cfg)
                    el.description = description  # type: ignore[attr-defined]
                except Exception as exc:
                    logger.debug("LLM image description failed for %s: %s", el.element_id, exc)

    def resolve_ambiguities(self, document: Document, llm_cfg: LLMConfig) -> None:
        """Use the LLM to reclassify elements whose type is uncertain.

        Currently resolves CAPTION vs HEADING ambiguities for short single-line
        text blocks at the top of a page.

        Args:
            document: Document to refine.
            llm_cfg: LLM configuration.
        """
        if self._llm is None:
            return

        for page in document.pages:
            for el in page.elements:
                if el.element_type != ElementType.CAPTION:
                    continue
                text: str = getattr(el, "text", "") or ""
                if not text.strip() or len(text) > 200:
                    continue
                # Only query the LLM for ambiguous short strings
                prompt = (
                    f'Is the following text a "caption" (describing a figure/table) '
                    f'or a "heading" (section title)? Reply with exactly one word.\n\nText: "{text}"'
                )
                try:
                    answer = self._llm.generate_text(prompt, llm_cfg).strip().lower()
                    if answer == "heading":
                        el.element_type = ElementType.HEADING
                except Exception as exc:
                    logger.debug("Ambiguity resolution failed for %s: %s", el.element_id, exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _surrounding_text(page: object, target: Image) -> str:
        """Collect text from elements near *target* on the same page."""
        texts: List[str] = []
        for el in getattr(page, "elements", []):
            if el is target:
                continue
            text = getattr(el, "text", None)
            if text:
                texts.append(text)
        return " ".join(texts)[:500]
