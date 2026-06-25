#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Provider Base - Abstract AI provider interface
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
    """Base provider class using only stdlib urllib for maximum compatibility
    (Windows XP/7/8/10/11, Linux, macOS, 32-bit and 64-bit)."""

    supports_native_tools = False

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int = 60, max_retries: int = 2):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        last_err = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code >= 500 and attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                raise ProviderError(f"HTTP {e.code}: {body}")
            except urllib.error.URLError as e:
                last_err = e.reason
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                raise ProviderError(f"Network error: {last_err}")
            except Exception as e:
                raise ProviderError(str(e))
        raise ProviderError(f"Network error: {last_err}")

    def _stream_post(self, endpoint: str, payload: Dict) -> Iterator[Dict]:
        """Stream SSE response. Yields dicts: {"type": "text", "text": str}
        or {"type": "tool_calls", "tool_calls": [...]} once fully assembled
        at the end of the stream (OpenAI-style deltas arrive as fragments
        across many chunks and must be reassembled before they're usable)."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        payload["stream"] = True
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        # Accumulator for partial tool_calls across chunks, keyed by index.
        tc_acc: Dict[int, Dict[str, Any]] = {}
        try:
            with urllib.request.urlopen(req, timeout=max(self.timeout, 120)) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choice = (obj.get("choices") or [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield {"type": "text", "text": content}
                    for tc in (delta.get("tool_calls") or []):
                        idx = tc.get("index", 0)
                        slot = tc_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] += fn["name"]
                        if fn.get("arguments"):
                            slot["arguments"] += fn["arguments"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Network error: {e.reason}")

        if tc_acc:
            calls = []
            for idx in sorted(tc_acc.keys()):
                slot = tc_acc[idx]
                try:
                    args = json.loads(slot["arguments"]) if slot["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                calls.append({"id": slot["id"], "name": slot["name"], "arguments": args})
            yield {"type": "tool_calls", "tool_calls": calls}

    def _post_get(self, endpoint: str) -> Dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=min(self.timeout, 15)) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {}

    def chat(self, messages: List[Dict], stream: bool = False, **kwargs) -> Any:
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return []

    def test_connection(self) -> bool:
        """Verify the API key/endpoint works. Tries the cheap models-list
        endpoint first (no token cost); only falls back to an actual chat
        completion if that's unavailable, since a real completion costs
        money on paid providers."""
        try:
            models = self.list_models()
            if models:
                return True
        except Exception:
            pass
        try:
            self.chat([{"role": "user", "content": "ping"}], stream=False, max_tokens=1)
            return True
        except Exception:
            return False


class ProviderError(Exception):
    pass


class OpenAICompatProvider(AIProvider):
    """Handles OpenRouter, Groq, OpenAI, Ollama (all OpenAI-compatible APIs)."""

    supports_native_tools = True

    def __init__(self, api_key: str, base_url: str, model: str,
                 extra_headers: Optional[Dict] = None,
                 timeout: int = 60, max_retries: int = 2):
        super().__init__(api_key, base_url, model, timeout, max_retries)
        self._extra_headers = extra_headers or {}

    def _headers(self) -> Dict[str, str]:
        h = super()._headers()
        h.update(self._extra_headers)
        return h

    def chat(self, messages: List[Dict], stream: bool = False,
             max_tokens: int = 4096, temperature: float = 0.7,
             tools: Optional[List[Dict]] = None, **kwargs) -> Any:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if stream:
            return self._stream_post("chat/completions", payload)
        else:
            resp = self._post("chat/completions", payload)
            message = resp["choices"][0]["message"]
            result = {"text": message.get("content") or "", "tool_calls": []}
            for tc in (message.get("tool_calls") or []):
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result["tool_calls"].append({"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": args})
            return result

    def list_models(self) -> List[str]:
        try:
            resp = self._post_get("models")
            return [m["id"] for m in resp.get("data", [])]
        except Exception:
            return []


class AnthropicProvider(AIProvider):
    """Native Anthropic Messages API."""

    supports_native_tools = True

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def list_models(self) -> List[str]:
        try:
            resp = self._post_get("models")
            return [m["id"] for m in resp.get("data", [])]
        except Exception:
            return []

    def chat(self, messages: List[Dict], stream: bool = False,
             max_tokens: int = 4096, temperature: float = 0.7,
             tools: Optional[List[Dict]] = None, **kwargs) -> Any:
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
        if tools:
            payload["tools"] = tools

        if stream:
            return self._stream_anthropic(payload)
        else:
            resp = self._post("messages", payload)
            text = ""
            calls = []
            for block in resp.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
                elif block.get("type") == "tool_use":
                    calls.append({"id": block.get("id", ""), "name": block.get("name", ""),
                                  "arguments": block.get("input", {})})
            return {"text": text, "tool_calls": calls}

    def _stream_anthropic(self, payload: Dict) -> Iterator[Dict]:
        """Yields {"type": "text", "text": str} during the stream, then a
        single {"type": "tool_calls", "tool_calls": [...]} at the end if any
        tool_use blocks were produced."""
        payload["stream"] = True
        url = f"{self.base_url}/messages"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        # Per-index accumulator for tool_use blocks (name set at block-start,
        # input arrives as fragmented partial_json across many deltas).
        blocks: Dict[int, Dict[str, Any]] = {}
        try:
            with urllib.request.urlopen(req, timeout=max(self.timeout, 120)) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    etype = obj.get("type")
                    if etype == "content_block_start":
                        cb = obj.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            blocks[obj["index"]] = {"id": cb.get("id", ""), "name": cb.get("name", ""), "json": ""}
                    elif etype == "content_block_delta":
                        delta = obj.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield {"type": "text", "text": delta.get("text", "")}
                        elif delta.get("type") == "input_json_delta":
                            idx = obj.get("index")
                            if idx in blocks:
                                blocks[idx]["json"] += delta.get("partial_json", "")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Network error: {e.reason}")

        if blocks:
            calls = []
            for idx in sorted(blocks.keys()):
                b = blocks[idx]
                try:
                    args = json.loads(b["json"]) if b["json"] else {}
                except json.JSONDecodeError:
                    args = {}
                calls.append({"id": b["id"], "name": b["name"], "arguments": args})
            yield {"type": "tool_calls", "tool_calls": calls}


def create_provider(provider_name: str, api_key: str, model: str,
                     timeout: int = 60, max_retries: int = 2,
                     base_url_override: Optional[str] = None) -> AIProvider:
    """Factory function to create the right provider."""
    from src.core.config import PROVIDERS
    info = PROVIDERS.get(provider_name, PROVIDERS["openrouter"])
    base_url = base_url_override or info["base_url"]

    if provider_name == "anthropic":
        return AnthropicProvider(api_key, base_url, model, timeout, max_retries)
    elif provider_name == "openrouter":
        extra = {
            "HTTP-Referer": "https://github.com/Zelvior/AIdex",
            "X-Title": "AIdex AI Coding Agent",
        }
        return OpenAICompatProvider(api_key, base_url, model, extra, timeout, max_retries)
    elif provider_name == "ollama":
        # Ollama needs no real auth; harmless dummy bearer token is sent.
        return OpenAICompatProvider(api_key or "local", base_url, model, None, timeout, max_retries)
    else:
        return OpenAICompatProvider(api_key, base_url, model, None, timeout, max_retries)
