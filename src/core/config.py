#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Config Manager - Handles API keys, model settings, preferences
Apache 2.0 License
"""

from __future__ import annotations
import os
import json
import platform
from pathlib import Path
from typing import Optional, Dict, Any


def get_config_dir() -> Path:
    """Return OS-appropriate config directory (cross-platform, 32/64-bit safe,
    Windows XP through Windows 11, Linux, macOS)."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "aidex"


def _legacy_config_dir() -> Path:
    """Old 'nexus-agent' config dir, kept for one-time migration only."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "nexus-agent"


CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
MODELS_CACHE_DIR = CONFIG_DIR / "models_cache"
_LEGACY_CONFIG_FILE = _legacy_config_dir() / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "openrouter",
    "model": "openai/gpt-3.5-turbo",
    "openrouter_api_key": "",
    "groq_api_key": "",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "ollama_api_key": "local",
    "ollama_base_url": "http://localhost:11434/v1",
    "theme": "dark",
    "max_tokens": 4096,
    "temperature": 0.7,
    "auto_save": True,
    "show_token_count": True,
    "max_history": 100,
    "workspace": str(Path.cwd()),
    "safe_mode": True,
    "stream": True,
    "plain_ui": False,
    "low_end_mode": False,
    "web_allow_shell_tools": False,
    "request_timeout": 60,
    "max_retries": 2,
}

PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_field": "openrouter_api_key",
        "free_models": [
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemma-2-9b-it:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "qwen/qwen-2-7b-instruct:free",
            "openchat/openchat-7b:free",
        ],
        "paid_models": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
            "anthropic/claude-3-5-sonnet",
            "anthropic/claude-3-haiku",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-70b-instruct",
            "mistralai/mixtral-8x7b-instruct",
            "cohere/command-r-plus",
        ],
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_field": "groq_api_key",
        "free_models": [
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "llama3-8b-8192",
            "llama3-70b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "gemma-7b-it",
        ],
        "paid_models": [],
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "key_field": "anthropic_api_key",
        "free_models": [],
        "paid_models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_field": "openai_api_key",
        "free_models": [],
        "paid_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "key_field": "ollama_api_key",
        "free_models": [
            "llama3.2:1b",
            "llama3.2",
            "qwen2.5:0.5b",
            "qwen2.5:1.5b",
            "phi3:mini",
            "gemma2:2b",
        ],
        "paid_models": [],
    },
}


class Config:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**DEFAULT_CONFIG, **saved}
            except (json.JSONDecodeError, IOError):
                self._data = dict(DEFAULT_CONFIG)
        elif _LEGACY_CONFIG_FILE.exists():
            # One-time migration from old Nexus config location
            try:
                with open(_LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**DEFAULT_CONFIG, **saved}
            except (json.JSONDecodeError, IOError):
                self._data = dict(DEFAULT_CONFIG)
        else:
            self._data = dict(DEFAULT_CONFIG)
        self.save()

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            pass  # Silently fail if can't write

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        """Return a shallow copy of all config values (callers should mask
        secrets themselves before exposing this externally, e.g. over HTTP)."""
        return dict(self._data)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()

    def get_api_key(self, provider: Optional[str] = None) -> str:
        p = provider or self._data.get("provider", "openrouter")
        field = PROVIDERS.get(p, {}).get("key_field", "")
        key = self._data.get(field, "")
        if p == "ollama" and not key:
            return "local"
        return key

    def set_api_key(self, provider: str, key: str):
        field = PROVIDERS.get(provider, {}).get("key_field", "")
        if field:
            self._data[field] = key
            self.save()

    def get_provider_info(self, provider: Optional[str] = None) -> Dict:
        p = provider or self._data.get("provider", "openrouter")
        info = dict(PROVIDERS.get(p, PROVIDERS["openrouter"]))
        if p == "ollama":
            info["base_url"] = self._data.get("ollama_base_url", info["base_url"])
        return info

    def all_models(self, provider: Optional[str] = None) -> list:
        info = self.get_provider_info(provider)
        return info.get("free_models", []) + info.get("paid_models", [])

    def get_live_models(self, provider: Optional[str] = None, force_refresh: bool = False,
                         timeout: Optional[int] = None):
        """Return (models: List[ModelInfo], source: str) using the real
        provider API, with disk caching for offline/low-end resilience.
        Falls back to the static built-in list (as ModelInfo) on total failure."""
        from src.core.models import get_models, ModelInfo
        p = provider or self.provider
        info = self.get_provider_info(p)
        api_key = self.get_api_key(p)
        try:
            models, source = get_models(
                p, api_key, info["base_url"], MODELS_CACHE_DIR,
                timeout=timeout or int(self.get("request_timeout", 60)),
                force_refresh=force_refresh,
            )
            return models, source
        except Exception:
            static = [ModelInfo(id=m, is_free=(m in info.get("free_models", [])))
                      for m in self.all_models(p)]
            return static, "static-fallback"

    def models_cache_age(self, provider: Optional[str] = None) -> str:
        from src.core.models import cache_age_label
        return cache_age_label(MODELS_CACHE_DIR, provider or self.provider)

    @property
    def provider(self) -> str:
        return self._data.get("provider", "openrouter")

    @property
    def model(self) -> str:
        return self._data.get("model", "openai/gpt-3.5-turbo")

    @property
    def workspace(self) -> str:
        ws = self._data.get("workspace", str(Path.cwd()))
        if not os.path.isdir(ws):
            ws = str(Path.cwd())
        return ws


# Global config instance
config = Config()
