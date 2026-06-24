"""OpenAI LLM provider implementation.

Wraps the official ``openai`` Python SDK to provide GPT-4 text generation
and GPT-4V vision generation for the SemanticEnhancer and ImageProcessor
stages (Requirement 8: Semantic Enhancement).

Requires:
    pip install openai
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Optional

from PIL import Image as PILImage

from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.models.config import LLMConfig

__all__ = ["OpenAIProvider"]

logger = logging.getLogger(__name__)

# Rough characters-per-token ratio for token estimation without tiktoken.
_CHARS_PER_TOKEN = 4


class OpenAIProvider(LLMProvider):
    """LLM provider backed by the OpenAI API.

    Supports text generation (GPT-4 class models) and vision generation
    (GPT-4V / GPT-4o).  API calls are retried up to *max_retries* times
    with the SDK's built-in exponential backoff.

    The ``openai.OpenAI`` client is created lazily on the first generation
    call so that importing the module is cheap.

    Args:
        api_key: OpenAI API key.  Falls back to the ``OPENAI_API_KEY``
            environment variable if ``None``.
        max_retries: Number of automatic retries on transient errors
            (rate limits, server errors).
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
        return "openai"

    def generate_text(self, prompt: str, config: LLMConfig) -> str:
        """Send *prompt* to the configured OpenAI chat model.

        Args:
            prompt: Instruction text.
            config: Active LLM configuration; ``config.model``,
                ``config.max_tokens``, and temperature-equivalent fields
                are forwarded to the API.

        Returns:
            Model response string.

        Raises:
            openai.OpenAIError: On unrecoverable API errors after retries.
        """
        client = self._get_client()
        try:
            response = client.chat.completions.create(  # type: ignore[union-attr]
                model=config.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI generate_text failed: %s", exc)
            raise

    def generate_with_vision(
        self, prompt: str, image: PILImage.Image, config: LLMConfig
    ) -> str:
        """Send *prompt* and *image* to a GPT-4V / GPT-4o vision model.

        The image is base64-encoded as PNG and inlined in the message
        content using the OpenAI vision message format.

        Args:
            prompt: Question or instruction about the image.
            image: PIL image to analyse.
            config: Active LLM configuration.

        Returns:
            Model response string.

        Raises:
            openai.OpenAIError: On unrecoverable API errors after retries.
        """
        client = self._get_client()
        image_b64 = self._image_to_base64(image)
        try:
            response = client.chat.completions.create(  # type: ignore[union-attr]
                model=config.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=config.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI generate_with_vision failed: %s", exc)
            raise

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a characters-per-token heuristic.

        For precise counts use ``tiktoken``; this approximation (4 chars ≈
        1 token) is sufficient for budget checks.

        Args:
            text: Text to estimate.

        Returns:
            Approximate token count.
        """
        return max(1, len(text) // _CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> object:
        if self._client is None:
            import openai  # lazy import

            self._client = openai.OpenAI(
                api_key=self._api_key,
                max_retries=self._max_retries,
            )
        return self._client

    @staticmethod
    def _image_to_base64(image: PILImage.Image) -> str:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
