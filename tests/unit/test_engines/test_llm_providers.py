"""Unit tests for LLM provider implementations (task 7.3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from smart_pdf_scanner.engines.llm.base import LLMProvider
from smart_pdf_scanner.models.config import LLMConfig


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(
        provider="openai",
        model="gpt-4-turbo",
        max_tokens=256,
        temperature=0.0,
    )


@pytest.fixture
def anthropic_config() -> LLMConfig:
    return LLMConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        max_tokens=256,
        temperature=0.0,
    )


@pytest.fixture
def sample_image() -> PILImage.Image:
    return PILImage.new("RGB", (100, 100), color=(200, 200, 200))


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class TestLLMProviderInterface:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    def _make_provider(self, api_key: str = "test-key") -> "object":
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider
        return OpenAIProvider(api_key=api_key)

    def test_name(self) -> None:
        assert self._make_provider().name == "openai"  # type: ignore[attr-defined]

    def test_estimate_tokens_nonempty(self) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider
        provider = OpenAIProvider()
        # "hello" = 5 chars → 5 // 4 = 1; minimum is 1
        assert provider.estimate_tokens("hello") >= 1

    def test_estimate_tokens_longer_text(self) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider
        provider = OpenAIProvider()
        text = "word " * 100  # 500 chars → ~125 tokens
        assert provider.estimate_tokens(text) >= 100

    def test_estimate_tokens_empty_returns_at_least_one(self) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider
        assert OpenAIProvider().estimate_tokens("") >= 1

    def test_generate_text_returns_response(
        self, llm_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Generated text response"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="key")
            result = provider.generate_text("Hello?", llm_config)
        assert result == "Generated text response"

    def test_generate_text_api_error_propagates(
        self, llm_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="key")
            with pytest.raises(RuntimeError, match="API error"):
                provider.generate_text("Hello?", llm_config)

    def test_generate_with_vision_returns_response(
        self, llm_config: LLMConfig, sample_image: PILImage.Image
    ) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Vision response"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="key")
            result = provider.generate_with_vision("Describe?", sample_image, llm_config)
        assert result == "Vision response"

    def test_generate_text_empty_content_returns_empty_string(
        self, llm_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices[0].message.content = None
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="key")
            result = provider.generate_text("Hello?", llm_config)
        assert result == ""

    def test_client_created_lazily(self) -> None:
        from smart_pdf_scanner.engines.llm.openai import OpenAIProvider
        provider = OpenAIProvider(api_key="key")
        assert provider._client is None  # not created yet


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    def test_name(self) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider
        assert AnthropicProvider().name == "anthropic"

    def test_estimate_tokens(self) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider
        provider = AnthropicProvider()
        assert provider.estimate_tokens("hello") >= 1
        assert provider.estimate_tokens("word " * 100) >= 100

    def test_generate_text_returns_response(
        self, anthropic_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider

        mock_message = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Claude response"
        mock_message.content = [mock_content]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="key")
            result = provider.generate_text("Hello?", anthropic_config)
        assert result == "Claude response"

    def test_generate_text_empty_content_returns_empty(
        self, anthropic_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider

        mock_message = MagicMock()
        mock_message.content = []
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="key")
            result = provider.generate_text("Hello?", anthropic_config)
        assert result == ""

    def test_generate_text_api_error_propagates(
        self, anthropic_config: LLMConfig
    ) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API error")
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="key")
            with pytest.raises(RuntimeError, match="API error"):
                provider.generate_text("Hello?", anthropic_config)

    def test_generate_with_vision_sends_image(
        self, anthropic_config: LLMConfig, sample_image: PILImage.Image
    ) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider

        mock_message = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Vision answer"
        mock_message.content = [mock_content]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="key")
            result = provider.generate_with_vision("Describe?", sample_image, anthropic_config)
        assert result == "Vision answer"
        # Verify the image was passed in the messages
        call_kwargs = mock_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        content = messages[0]["content"]
        image_block = next(b for b in content if b.get("type") == "image")
        assert image_block["source"]["type"] == "base64"
        assert image_block["source"]["media_type"] == "image/png"

    def test_client_created_lazily(self) -> None:
        from smart_pdf_scanner.engines.llm.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key="key")
        assert provider._client is None
