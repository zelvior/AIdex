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
    "provider": "pollinations",
    "model": "openai",
    "openrouter_api_key": "",
    "groq_api_key": "",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "ollama_api_key": "local",
    "ollama_base_url": "http://localhost:11434/v1",
    "gemini_api_key": "",
    "pollinations_api_key": "",
    "custom_api_key": "",
    "custom_base_url": "",
    "custom_chat_model": "",
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
    # Image generation is configured independently of chat — e.g. you can
    # chat via OpenRouter and still generate images via Pollinations (the
    # zero-config default) without switching your chat provider.
    "image_provider": "pollinations",
    "image_model": "flux",
    "image_api_key": "",
    "image_base_url": "",
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
        "requires_key": False,
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
    "pollinations": {
        # No API key required for normal use — free, no signup, generous
        # quota. This is AIdex's zero-config default: a brand new user can
        # chat AND generate images without ever opening /config.
        # https://github.com/pollinations/pollinations
        "name": "Pollinations (Free, No Key Needed)",
        "base_url": "https://gen.pollinations.ai/v1",
        "key_field": "pollinations_api_key",
        "requires_key": False,
        "free_models": [
            "openai",
            "openai-fast",
            "mistral",
            "llama",
            "deepseek",
            "qwen-coder",
        ],
        "paid_models": [],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_field": "gemini_api_key",
        "free_models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ],
        "paid_models": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ],
    },
    "custom": {
        # User-defined OpenAI-compatible endpoint — covers literally any
        # provider with a /chat/completions-shaped API that isn't already
        # built in (self-hosted, a company gateway, a new provider, etc.)
        "name": "Custom (Any OpenAI-Compatible API)",
        "base_url": "",  # filled in from config.custom_base_url at use time
        "key_field": "custom_api_key",
        "free_models": [],
        "paid_models": [],
    },
}

# Image generation providers — separate registry from chat PROVIDERS above,
# since the image backend is configured independently (you might chat via
# OpenRouter but still generate images via the free Pollinations default).
IMAGE_PROVIDERS = {
    "pollinations": {
        # Free, unlimited for normal use, no signup or key required.
        # GET https://image.pollinations.ai/prompt/{prompt}?model=&width=&height=&seed=&nologo=
        "name": "Pollinations (Free, No Key Needed)",
        "base_url": "https://image.pollinations.ai/prompt",
        "key_field": "image_api_key",
        "requires_key": False,
        "models": ["flux", "turbo", "kontext", "gptimage", "seedream", "nanobanana"],
    },
    "custom": {
        "name": "Custom (Any Image API)",
        "base_url": "",
        "key_field": "image_api_key",
        "models": [],
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
        p = provider or self._data.get("provider", "pollinations")
        field = PROVIDERS.get(p, {}).get("key_field", "")
        key = self._data.get(field, "")
        if not key and not PROVIDERS.get(p, {}).get("requires_key", True):
            return "not-needed"
        return key

    def needs_api_key(self, provider: Optional[str] = None) -> bool:
        """True if this provider actually requires a key to be set (as
        opposed to ones like Pollinations/Ollama that work with none)."""
        p = provider or self._data.get("provider", "pollinations")
        return bool(PROVIDERS.get(p, {}).get("requires_key", True))

    def has_usable_key(self, provider: Optional[str] = None) -> bool:
        """True if this provider is ready to use right now — either it
        doesn't need a key, or a real key has been set."""
        p = provider or self._data.get("provider", "pollinations")
        if not self.needs_api_key(p):
            return True
        field = PROVIDERS.get(p, {}).get("key_field", "")
        return bool(self._data.get(field, ""))

    def set_api_key(self, provider: str, key: str):
        field = PROVIDERS.get(provider, {}).get("key_field", "")
        if field:
            self._data[field] = key
            self.save()

    def get_provider_info(self, provider: Optional[str] = None) -> Dict:
        p = provider or self._data.get("provider", "pollinations")
        info = dict(PROVIDERS.get(p, PROVIDERS["pollinations"]))
        if p == "ollama":
            info["base_url"] = self._data.get("ollama_base_url", info["base_url"])
        elif p == "custom":
            info["base_url"] = self._data.get("custom_base_url", "")
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

    def get_image_provider_info(self, provider: Optional[str] = None) -> Dict:
        p = provider or self.get("image_provider", "pollinations")
        info = dict(IMAGE_PROVIDERS.get(p, IMAGE_PROVIDERS["pollinations"]))
        if p == "custom":
            info["base_url"] = self.get("image_base_url", "")
        return info

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1024,
                        seed: Optional[int] = None, timeout: Optional[int] = None):
        """Generate an image using the configured image provider — free
        Pollinations by default, no API key or setup required."""
        from src.core.imagegen import generate_image as _generate_image
        p = self.get("image_provider", "pollinations")
        info = self.get_image_provider_info(p)
        api_key = self.get(info.get("key_field", "image_api_key"), "")
        model = self.get("image_model", "flux")
        return _generate_image(
            prompt, p, info["base_url"], api_key, model, width, height, seed,
            timeout=timeout or int(self.get("request_timeout", 60)),
        )

    @property
    def provider(self) -> str:
        return self._data.get("provider", "pollinations")

    @property
    def model(self) -> str:
        return self._data.get("model", "openai")

    @property
    def workspace(self) -> str:
        ws = self._data.get("workspace", str(Path.cwd()))
        if not os.path.isdir(ws):
            ws = str(Path.cwd())
        return ws


# Global config instance
config = Config()
