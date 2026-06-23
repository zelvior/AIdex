#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus Provider Base - Abstract AI provider interface
Apache 2.0 License
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Iterator, List, Dict, Any, Optional


class AIProvider:
    """Base provider class using only stdlib urllib for maximum compatibility."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Network error: {e.reason}")
        except Exception as e:
            raise ProviderError(str(e))

    def _stream_post(self, endpoint: str, payload: Dict) -> Iterator[str]:
        """Stream SSE response, yielding text deltas."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        payload["stream"] = True
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                        delta = (obj.get("choices", [{}])[0]
                                   .get("delta", {})
                                   .get("content", ""))
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, IndexError):
                        continue
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Network error: {e.reason}")

    def chat(self, messages: List[Dict], stream: bool = False, **kwargs) -> Any:
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return []

    def test_connection(self) -> bool:
        try:
            self.chat([{"role": "user", "content": "ping"}], stream=False)
            return True
        except Exception:
            return False


class ProviderError(Exception):
    pass


class OpenAICompatProvider(AIProvider):
    """Handles OpenRouter, Groq, OpenAI (all OpenAI-compatible APIs)."""

    def __init__(self, api_key: str, base_url: str, model: str, extra_headers: Optional[Dict] = None):
        super().__init__(api_key, base_url, model)
        self._extra_headers = extra_headers or {}

    def _headers(self) -> Dict[str, str]:
        h = super()._headers()
        h.update(self._extra_headers)
        return h

    def chat(self, messages: List[Dict], stream: bool = False,
             max_tokens: int = 4096, temperature: float = 0.7, **kwargs) -> Any:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stream:
            return self._stream_post("chat/completions", payload)
        else:
            resp = self._post("chat/completions", payload)
            return resp["choices"][0]["message"]["content"]

    def list_models(self) -> List[str]:
        try:
            resp = self._post_get("models")
            return [m["id"] for m in resp.get("data", [])]
        except Exception:
            return []

    def _post_get(self, endpoint: str) -> Dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {}


class AnthropicProvider(AIProvider):
    """Native Anthropic Messages API."""

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def chat(self, messages: List[Dict], stream: bool = False,
             max_tokens: int = 4096, temperature: float = 0.7, **kwargs) -> Any:
        # Separate system message if present
        system = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append(m)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": filtered,
            "max_tokens": max_tokens,
        }
        if system:
            payload["system"] = system

        if stream:
            return self._stream_anthropic(payload)
        else:
            resp = self._post("messages", payload)
            return resp["content"][0]["text"]

    def _stream_anthropic(self, payload: Dict) -> Iterator[str]:
        payload["stream"] = True
        url = f"{self.base_url}/messages"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    try:
                        obj = json.loads(chunk)
                        if obj.get("type") == "content_block_delta":
                            yield obj.get("delta", {}).get("text", "")
                    except json.JSONDecodeError:
                        continue
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {e.code}: {body}")


def create_provider(provider_name: str, api_key: str, model: str) -> AIProvider:
    """Factory function to create the right provider."""
    from src.core.config import PROVIDERS
    info = PROVIDERS.get(provider_name, PROVIDERS["openrouter"])
    base_url = info["base_url"]

    if provider_name == "anthropic":
        return AnthropicProvider(api_key, base_url, model)
    elif provider_name == "openrouter":
        extra = {
            "HTTP-Referer": "https://github.com/nexus-agent",
            "X-Title": "Nexus AI Coding Agent",
        }
        return OpenAICompatProvider(api_key, base_url, model, extra)
    else:
        return OpenAICompatProvider(api_key, base_url, model)
