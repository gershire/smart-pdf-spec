"""LLM provider base interface.

Defines the abstract contract that all LLM provider implementations must
follow (Requirement 8: Semantic Enhancement).

Provider implementations live in sibling modules:
- ``openai.py``    — OpenAI GPT-4 / GPT-4V provider
- ``anthropic.py`` — Anthropic Claude provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image as PILImage

from smart_pdf_scanner.models.config import LLMConfig

__all__ = ["LLMProvider"]


class LLMProvider(ABC):
    """Abstract interface for LLM provider implementations.

    Providers support two generation modes:

    * **Text-only** (:meth:`generate_text`): prompt → text, used for heading
      hierarchy refinement and structural ambiguity resolution.
    * **Vision** (:meth:`generate_with_vision`): prompt + image → text, used
      for generating image descriptions in the
      :class:`~smart_pdf_scanner.stages.image_processor.ImageProcessor` and
      :class:`~smart_pdf_scanner.stages.semantic_enhancer.SemanticEnhancer`
      stages.

    :meth:`estimate_tokens` enables token-budget tracking so the pipeline
    can cap LLM costs per document.

    Implementing a new provider requires:
    1. Subclass :class:`LLMProvider`.
    2. Implement :meth:`generate_text`, :meth:`generate_with_vision`, and
       :meth:`estimate_tokens`.
    3. Expose a unique identifier via the :attr:`name` property.

    Example::

        class MyProvider(LLMProvider):
            @property
            def name(self) -> str:
                return "my_provider"

            def generate_text(self, prompt, config):
                ...

            def generate_with_vision(self, prompt, image, config):
                ...

            def estimate_tokens(self, text):
                ...
    """

    @abstractmethod
    def generate_text(self, prompt: str, config: LLMConfig) -> str:
        """Generate a text completion for *prompt*.

        Args:
            prompt: The full prompt string to send to the model.
            config: Active LLM configuration (model name, max tokens,
                temperature, API key, etc.).

        Returns:
            The model's response as a plain string.

        Raises:
            Exception: Provider-specific exceptions on API errors; callers
                should catch and handle with fallback logic.
        """

    @abstractmethod
    def generate_with_vision(
        self, prompt: str, image: PILImage.Image, config: LLMConfig
    ) -> str:
        """Generate a text response conditioned on *prompt* and *image*.

        Args:
            prompt: Instruction or question about the image.
            image: PIL image to send to the vision model.
            config: Active LLM configuration.

        Returns:
            The model's response as a plain string.

        Raises:
            NotImplementedError: If the underlying model does not support
                vision inputs.
        """

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate the token count for *text* under this provider's tokeniser.

        Used for cost tracking and prompt budgeting before making API calls.

        Args:
            text: The string to estimate.

        Returns:
            Approximate token count (integer).
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier used in logging and configuration."""
