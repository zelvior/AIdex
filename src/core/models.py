#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Model Registry - Live model discovery with disk caching.
Apache 2.0 License

Fetches the real, current model list (with pricing and context length
where available) directly from each provider's API instead of relying
on a hardcoded list that goes stale. Results are cached to disk so
AIdex still has a usable model list when offline or rate-limited, and
so low-end devices aren't forced to hit the network on every startup.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours — models/pricing don't change every minute


class ModelInfo:
    """Normalized model record used across all providers."""

    __slots__ = ("id", "name", "context_length", "prompt_price", "completion_price",
                 "is_free", "supports_tools", "raw")

    def __init__(self, id, name="", context_length=0, prompt_price=None,
                 completion_price=None, is_free=False, supports_tools=None, raw=None):
        self.id = id
        self.name = name or id
        self.context_length = context_length or 0
        self.prompt_price = prompt_price      # float, USD per 1M tokens, or None if unknown
        self.completion_price = completion_price
        self.is_free = is_free
        self.supports_tools = supports_tools  # True/False/None (unknown)
        self.raw = raw or {}

    def price_label(self) -> str:
        if self.is_free:
            return "FREE"
        if self.prompt_price is None:
            return "?"
        # prices stored as USD per 1M tokens
        if self.prompt_price == 0 and (self.completion_price or 0) == 0:
            return "FREE"
        return "$%.2f/$%.2f per 1M" % (self.prompt_price, self.completion_price or 0)

    def context_label(self) -> str:
        if not self.context_length:
            return "?"
        if self.context_length >= 1000:
            return "%dK" % (self.context_length // 1000)
        return str(self.context_length)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "context_length": self.context_length,
            "prompt_price": self.prompt_price, "completion_price": self.completion_price,
            "is_free": self.is_free, "supports_tools": self.supports_tools,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelInfo":
        return cls(
            id=d.get("id", ""), name=d.get("name", ""),
            context_length=d.get("context_length", 0),
            prompt_price=d.get("prompt_price"), completion_price=d.get("completion_price"),
            is_free=d.get("is_free", False), supports_tools=d.get("supports_tools"),
        )


def _get(url: str, headers: Dict[str, str], timeout: int = 15) -> Dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_openrouter(data: Dict) -> List[ModelInfo]:
    out = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {}) or {}
        try:
            prompt_p = float(pricing.get("prompt", "0") or "0") * 1_000_000
            completion_p = float(pricing.get("completion", "0") or "0") * 1_000_000
        except (TypeError, ValueError):
            prompt_p = completion_p = None
        is_free = (m.get("id", "").endswith(":free")) or (prompt_p == 0 and completion_p == 0)
        params = m.get("supported_parameters") or []
        out.append(ModelInfo(
            id=m.get("id", ""), name=m.get("name", m.get("id", "")),
            context_length=m.get("context_length", 0) or 0,
            prompt_price=prompt_p, completion_price=completion_p,
            is_free=is_free,
            supports_tools=("tools" in params) if params else None,
            raw=m,
        ))
    return out


def _parse_openai_style(data: Dict) -> List[ModelInfo]:
    """Groq / OpenAI / Ollama — minimal /v1/models schema, usually no pricing."""
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        ctx = m.get("context_window") or m.get("context_length") or 0
        out.append(ModelInfo(id=mid, name=mid, context_length=ctx, raw=m))
    return out


def _parse_anthropic(data: Dict) -> List[ModelInfo]:
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        name = m.get("display_name", mid)
        out.append(ModelInfo(id=mid, name=name, raw=m))
    return out


def fetch_live_models(provider: str, api_key: str, base_url: str, timeout: int = 15) -> List[ModelInfo]:
    """Hit the provider's real API and return a live model list.
    Raises on failure — caller decides whether to fall back to cache/static."""
    base_url = base_url.rstrip("/")

    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        data = _get(f"{base_url}/models", headers, timeout)
        return _parse_anthropic(data)

    # OpenAI-compatible providers: openrouter, groq, openai, ollama
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    data = _get(f"{base_url}/models", headers, timeout)
    if provider == "openrouter":
        return _parse_openrouter(data)
    return _parse_openai_style(data)


def _cache_path(cache_dir: Path, provider: str) -> Path:
    return cache_dir / ("models_%s.json" % provider)


def load_cached_models(cache_dir: Path, provider: str) -> Optional[Dict[str, Any]]:
    path = _cache_path(cache_dir, provider)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def save_cached_models(cache_dir: Path, provider: str, models: List[ModelInfo]):
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, provider)
    payload = {
        "fetched_at": time.time(),
        "models": [m.to_dict() for m in models],
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except IOError:
        pass


def get_models(provider: str, api_key: str, base_url: str, cache_dir: Path,
                timeout: int = 15, force_refresh: bool = False):
    """Main entry point: try live fetch, fall back to cache on failure.
    Returns (models, source) where source is one of 'live', 'cache', 'stale-cache'."""
    cached = load_cached_models(cache_dir, provider)
    cache_age = None
    if cached:
        cache_age = time.time() - cached.get("fetched_at", 0)

    if not force_refresh and cached and cache_age is not None and cache_age < CACHE_TTL_SECONDS:
        return [ModelInfo.from_dict(d) for d in cached["models"]], "cache"

    try:
        live = fetch_live_models(provider, api_key, base_url, timeout)
        if live:
            save_cached_models(cache_dir, provider, live)
            return live, "live"
        raise ValueError("empty model list returned")
    except Exception:
        if cached:
            return [ModelInfo.from_dict(d) for d in cached["models"]], "stale-cache"
        raise


def filter_models(models: List[ModelInfo], query: str = "", free_only: bool = False) -> List[ModelInfo]:
    """Simple case-insensitive substring filter on id/name, plus optional
    free-tier filter. Shared by both the Rich and plain TUIs."""
    out = models
    if free_only:
        out = [m for m in out if m.is_free]
    if query:
        q = query.lower()
        out = [m for m in out if q in m.id.lower() or q in m.name.lower()]
    return out


def sort_models(models: List[ModelInfo], by: str = "name") -> List[ModelInfo]:
    """by: 'name', 'price' (cheapest first, free first), 'context' (largest first)."""
    if by == "price":
        def key(m):
            if m.is_free:
                return (0, 0.0)
            if m.prompt_price is None:
                return (2, 0.0)
            return (1, m.prompt_price)
        return sorted(models, key=key)
    if by == "context":
        return sorted(models, key=lambda m: -(m.context_length or 0))
    return sorted(models, key=lambda m: m.id.lower())


def cache_age_label(cache_dir: Path, provider: str) -> str:
    cached = load_cached_models(cache_dir, provider)
    if not cached:
        return "no cache"
    age = time.time() - cached.get("fetched_at", 0)
    if age < 60:
        return "just now"
    if age < 3600:
        return "%dm ago" % (age // 60)
    if age < 86400:
        return "%dh ago" % (age // 3600)
    return "%dd ago" % (age // 86400)
