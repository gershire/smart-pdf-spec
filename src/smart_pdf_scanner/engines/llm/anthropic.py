"""Anthropic Claude LLM provider implementation.

Wraps the official ``anthropic`` Python SDK to provide Claude text and
vision generation for the SemanticEnhancer and ImageProcessor stages
(Requirement 8: Semantic Enhancement).

Requires:
    pip install anthropic
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Optional

from PIL import Image as PILImage

from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.models.config import LLMConfig

__all__ = ["AnthropicProvider"]

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(LLMProvider):
    """LLM provider backed by the Anthropic Claude API.

    Supports both text-only and vision (image + text) generation using the
    Messages API.  The Anthropic client is created lazily on first use.

    Args:
        api_key: Anthropic API key.  Falls back to the ``ANTHROPIC_API_KEY``
            environment variable if ``None``.
        max_retries: Number of automatic retries on transient errors.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._client: Optional[object] = None

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "anthropic"

    def generate_text(self, prompt: str, config: LLMConfig) -> str:
        """Send *prompt* to the configured Claude model.

        Args:
            prompt: Instruction text.
            config: Active LLM configuration; ``config.model`` and
                ``config.max_tokens`` are forwarded to the API.

        Returns:
            Model response string.

        Raises:
            anthropic.APIError: On unrecoverable API errors after retries.
        """
        client = self._get_client()
        model = config.model or _DEFAULT_MODEL
        try:
            message = client.messages.create(  # type: ignore[union-attr]
                model=model,
                max_tokens=config.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text if message.content else ""
        except Exception as exc:
            logger.error("Anthropic generate_text failed: %s", exc)
            raise

    def generate_with_vision(
        self, prompt: str, image: PILImage.Image, config: LLMConfig
    ) -> str:
        """Send *prompt* and *image* to a Claude vision model.

        The image is base64-encoded as PNG and included in the message
        using Anthropic's image content block format.

        Args:
            prompt: Question or instruction about the image.
            image: PIL image to analyse.
            config: Active LLM configuration.

        Returns:
            Model response string.

        Raises:
            anthropic.APIError: On unrecoverable API errors after retries.
        """
        client = self._get_client()
        model = config.model or _DEFAULT_MODEL
        image_b64 = self._image_to_base64(image)
        try:
            message = client.messages.create(  # type: ignore[union-attr]
                model=model,
                max_tokens=config.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return message.content[0].text if message.content else ""
        except Exception as exc:
            logger.error("Anthropic generate_with_vision failed: %s", exc)
            raise

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a characters-per-token heuristic.

        Args:
            text: Text to estimate.

        Returns:
            Approximate token count (4 chars ≈ 1 token).
        """
        return max(1, len(text) // _CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> object:
        if self._client is None:
            import anthropic  # lazy import

            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                max_retries=self._max_retries,
            )
        return self._client

    @staticmethod
    def _image_to_base64(image: PILImage.Image) -> str:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
