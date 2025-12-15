"""LLM adapter for content generation (Gemini/OpenAI)."""

from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate text from prompt."""
        pass


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider."""

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.llm_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(self, prompt: str) -> str:
        """Generate text using Gemini API."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        url = f"{self.base_url}/models/{self.model}:generateContent"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 4096,
                    },
                },
            )

            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.status_code} - {response.text}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise Exception("No response from Gemini")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise Exception("Empty response from Gemini")

            return parts[0].get("text", "")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.llm_model if "gpt" in settings.llm_model else "gpt-4"
        self.base_url = "https://api.openai.com/v1"

    async def generate(self, prompt: str) -> str:
        """Generate text using OpenAI API."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that generates JSON responses."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
            )

            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise Exception("No response from OpenAI")

            return choices[0].get("message", {}).get("content", "")


class LLMAdapter:
    """Adapter that selects appropriate LLM provider."""

    def __init__(self, provider: str | None = None) -> None:
        provider = provider or settings.llm_provider

        if provider == "gemini":
            self._provider = GeminiProvider()
        elif provider == "openai":
            self._provider = OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    async def generate(self, prompt: str) -> str:
        """Generate text using configured provider."""
        return await self._provider.generate(prompt)


# Alias for backward compatibility
LLMClient = LLMAdapter
