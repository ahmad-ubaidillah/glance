"""LLM Client Factory - Abstraction layer for multiple LLM providers.

Supports:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- ZhipuAI (GLM)
- Azure OpenAI
- Ollama (local)
- And other OpenAI-compatible APIs
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator

import httpx


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    ZHIPUAI = "zhipuai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int] | None = None
    raw_response: Any = None


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name (provider-specific).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse with content and metadata.
        """
        pass

    @abstractmethod
    async def chat_streaming(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Send a streaming chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            **kwargs: Additional provider-specific parameters.

        Yields:
            LLMResponse chunks.
        """
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible client (OpenAI, ZhipuAI, Ollama, custom)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        timeout: float = 60.0,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize OpenAI-compatible client.

        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API.
            model: Default model to use.
            timeout: Request timeout in seconds.
            default_headers: Additional headers to send with requests.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model
        self.timeout = timeout
        self.default_headers = default_headers or {}
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    **self.default_headers,
                },
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request with retry on rate limit."""
        model = model or self.default_model

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    "/chat/completions",
                    json=payload,
                )

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        import asyncio

                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()

                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=model,
                    provider=LLMProvider.OPENAI,
                    usage=data.get("usage"),
                    raw_response=data,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    import asyncio

                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise

    async def chat_streaming(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Send streaming chat completion request."""
        model = model or self.default_model

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        async with self.client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = data.strip()
                    if chunk:
                        import json

                        try:
                            parsed = json.loads(chunk)
                            content = parsed["choices"][0]["delta"].get("content", "")
                            if content:
                                yield LLMResponse(
                                    content=content,
                                    model=model,
                                    provider=LLMProvider.OPENAI,
                                )
                        except json.JSONDecodeError:
                            pass

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> None:
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key.
            model: Default Claude model.
            max_tokens: Max tokens in response.
            timeout: Request timeout.
        """
        self.api_key = api_key
        self.default_model = model
        self.default_max_tokens = max_tokens
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.anthropic.com",
                timeout=self.timeout,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request to Anthropic."""
        model = model or self.default_model

        # Convert messages to Anthropic format
        # Anthropic uses 'system' role differently
        system_message = ""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append(msg)

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        if system_message:
            payload["system"] = system_message

        response = await self.client.post(
            "/v1/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["content"][0]["text"],
            model=model,
            provider=LLMProvider.ANTHROPIC,
            usage=data.get("usage"),
            raw_response=data,
        )

    async def chat_streaming(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Streaming not supported for Anthropic in this implementation."""
        # For simplicity, fall back to non-streaming
        response = await self.chat(messages, model, temperature, max_tokens, **kwargs)
        yield response

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class GoogleClient(BaseLLMClient):
    """Google Gemini client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        timeout: float = 60.0,
    ) -> None:
        """Initialize Google Gemini client.

        Args:
            api_key: Google AI API key.
            model: Default Gemini model.
            timeout: Request timeout.
        """
        self.api_key = api_key
        self.default_model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request to Google Gemini."""
        model = model or self.default_model

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            if msg["role"] == "user":
                role = "user"
            elif msg["role"] == "assistant":
                role = "model"
            else:
                role = "user"  # Map system to user
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                **kwargs,
            },
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.GOOGLE,
            raw_response=data,
        )

    async def chat_streaming(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Streaming not fully implemented for Google."""
        response = await self.chat(messages, model, temperature, max_tokens, **kwargs)
        yield response

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Factory function
def create_llm_client(
    provider: LLMProvider | str,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> BaseLLMClient:
    """Create an LLM client based on provider.

    Args:
        provider: Provider name (enum or string).
        api_key: API key for the provider.
        model: Model name (provider-specific).
        base_url: Custom base URL for OpenAI-compatible APIs.
        **kwargs: Additional provider-specific arguments.

    Returns:
        BaseLLMClient instance.

    Raises:
        ValueError: If provider is unknown or required params missing.
    """
    if isinstance(provider, str):
        try:
            provider = LLMProvider(provider.lower())
        except ValueError:
            raise ValueError(f"Unknown provider: {provider}")

    # Get API key from environment if not provided
    if api_key is None:
        env_keys = {
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.GOOGLE: "GOOGLE_API_KEY",
            LLMProvider.ZHIPUAI: "ZHIPUAI_API_KEY",
            LLMProvider.AZURE_OPENAI: "AZURE_OPENAI_API_KEY",
            LLMProvider.OLLAMA: None,  # No API key for local
            LLMProvider.CUSTOM: "CUSTOM_API_KEY",
        }
        env_key = env_keys.get(provider)
        if env_key:
            api_key = os.getenv(env_key)

    if provider in (
        LLMProvider.OPENAI,
        LLMProvider.ZHIPUAI,
        LLMProvider.OLLAMA,
        LLMProvider.CUSTOM,
    ):
        # Default URLs for known providers
        default_urls = {
            LLMProvider.OPENAI: "https://api.openai.com/v1",
            LLMProvider.ZHIPUAI: "https://open.bigmodel.cn/api/paas/v4",
            LLMProvider.OLLAMA: "http://localhost:11434/v1",
        }
        base_url = base_url or default_urls.get(provider, "https://api.openai.com/v1")

        # Map common model names
        model = model or "gpt-4"
        if provider == LLMProvider.ZHIPUAI:
            model = model or "glm-4-flash"

        return OpenAIClient(
            api_key=api_key or "",
            base_url=base_url,
            model=model,
            **kwargs,
        )

    elif provider == LLMProvider.ANTHROPIC:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        model = model or "claude-3-sonnet-20240229"
        return AnthropicClient(api_key=api_key, model=model, **kwargs)

    elif provider == LLMProvider.GOOGLE:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google provider")
        model = model or "gemini-pro"
        return GoogleClient(api_key=api_key, model=model, **kwargs)

    elif provider == LLMProvider.AZURE_OPENAI:
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required for Azure OpenAI")
        base_url = base_url or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        if not base_url:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required for Azure OpenAI")
        model = model or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        return OpenAIClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            **kwargs,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")


# Adapter to make our LLM client compatible with existing agent code
class LLMClientAdapter:
    """Adapter to make our custom LLM client compatible with existing code.

    Wraps our BaseLLMClient to provide an OpenAI-like interface.
    """

    def __init__(self, client: BaseLLMClient) -> None:
        """Initialize the adapter.

        Args:
            client: Our custom LLM client.
        """
        self.client = client

    @property
    def chat(self):
        """Return completions object for chat.completions.create() compatibility."""
        return self

    @property
    def completions(self):
        """Return completions object for completions.create() compatibility."""
        return CompletionsAdapter(self.client)


class CompletionsAdapter:
    """Adapter for the completions.create() method."""

    def __init__(self, client: BaseLLMClient) -> None:
        self._client = client

    async def create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create chat completion (OpenAI-compatible interface)."""
        response = await self._client.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return {
            "choices": [
                {
                    "message": {
                        "content": response.content,
                        "role": "assistant",
                    },
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": response.usage
            or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "model": model,
        }


# Legacy method removed - using CompletionsAdapter now
