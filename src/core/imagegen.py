#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Image Generation - Free-by-default image generation, OpenRouter-style.
Apache 2.0 License

Default backend is Pollinations (https://pollinations.ai) — free, no
signup, no API key required for normal use, very high practical quota.
A "custom" backend lets the user point at any other image API that
either matches Pollinations' simple GET-prompt-in-URL shape or OpenAI's
images/generations JSON shape, configured the same way chat providers
are (base URL + optional key), so this isn't special-cased to one vendor.

Uses only the standard library (urllib) — no extra pip install, consistent
with the rest of AIdex's "zero hard dependencies" design.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, Tuple


class ImageGenError(Exception):
    pass


class ImageResult:
    """A generated image: raw bytes plus the info needed to save/display it."""

    def __init__(self, data: bytes, content_type: str = "image/jpeg",
                 prompt: str = "", model: str = "", seed: Optional[int] = None,
                 source_url: str = ""):
        self.data = data
        self.content_type = content_type
        self.prompt = prompt
        self.model = model
        self.seed = seed
        self.source_url = source_url

    def suggested_filename(self) -> str:
        ext = "png" if "png" in self.content_type else "jpg"
        ts = int(time.time())
        safe_prompt = "".join(c if c.isalnum() else "_" for c in self.prompt[:40]).strip("_") or "image"
        return f"{safe_prompt}_{ts}.{ext}"


def _http_get_bytes(url: str, headers: Dict[str, str], timeout: int = 60) -> Tuple[bytes, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return resp.read(), content_type
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise ImageGenError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise ImageGenError(f"Network error: {e.reason}")


def _http_post_json(url: str, headers: Dict[str, str], payload: Dict, timeout: int = 60) -> Dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise ImageGenError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise ImageGenError(f"Network error: {e.reason}")


def generate_image_pollinations(prompt: str, base_url: str, api_key: str = "",
                                 model: str = "flux", width: int = 1024,
                                 height: int = 1024, seed: Optional[int] = None,
                                 timeout: int = 60) -> ImageResult:
    """Pollinations' simple GET endpoint: the prompt is part of the URL
    path, parameters are query params, the response body IS the image.
    No API key needed for normal use — only helps with higher limits."""
    encoded_prompt = urllib.parse.quote(prompt)
    params = {
        "model": model,
        "width": str(width),
        "height": str(height),
        "nologo": "true",
    }
    if seed is not None:
        params["seed"] = str(seed)
    query = urllib.parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/{encoded_prompt}?{query}"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data, content_type = _http_get_bytes(url, headers, timeout)
    if not content_type.startswith("image/"):
        # Pollinations returns an error page (often HTML/JSON) on failure
        # rather than an HTTP error code in some cases — catch that here
        # so the caller gets a clear message instead of a corrupt image.
        snippet = data[:200].decode("utf-8", errors="replace")
        raise ImageGenError(f"Expected an image, got '{content_type}': {snippet}")

    return ImageResult(data, content_type, prompt=prompt, model=model, seed=seed, source_url=url)


def generate_image_openai_style(prompt: str, base_url: str, api_key: str,
                                 model: str = "dall-e-3", size: str = "1024x1024",
                                 timeout: int = 60) -> ImageResult:
    """OpenAI-style POST /images/generations — JSON request, JSON response
    containing either a URL or base64 data. Used for any 'custom' image
    API that follows the OpenAI images schema instead of Pollinations'
    simple GET-the-prompt shape."""
    import base64

    url = f"{base_url.rstrip('/')}/images/generations"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}

    resp = _http_post_json(url, headers, payload, timeout)
    items = resp.get("data", [])
    if not items:
        raise ImageGenError(f"No image returned: {json.dumps(resp)[:300]}")
    item = items[0]

    if "b64_json" in item:
        data = base64.b64decode(item["b64_json"])
        return ImageResult(data, "image/png", prompt=prompt, model=model)
    if "url" in item:
        img_data, content_type = _http_get_bytes(item["url"], {}, timeout)
        return ImageResult(img_data, content_type, prompt=prompt, model=model, source_url=item["url"])
    raise ImageGenError(f"Unrecognized image response shape: {json.dumps(item)[:300]}")


def generate_image(prompt: str, provider: str, base_url: str, api_key: str = "",
                    model: str = "flux", width: int = 1024, height: int = 1024,
                    seed: Optional[int] = None, timeout: int = 60) -> ImageResult:
    """Main entry point. Dispatches to the right backend shape based on
    provider — Pollinations' GET-prompt-in-path style by default, or
    OpenAI-images-JSON style for a custom endpoint that needs it."""
    if provider == "pollinations":
        return generate_image_pollinations(prompt, base_url, api_key, model, width, height, seed, timeout)
    elif provider == "custom":
        # A custom endpoint could be either shape. Prefer Pollinations-style
        # (GET, prompt-in-path) since that's the more common simple case;
        # the OpenAI-images shape is selected by base_url ending in a path
        # that looks like an API root rather than an image-prompt host.
        if base_url.rstrip("/").endswith(("/v1", "/openai")):
            return generate_image_openai_style(prompt, base_url, api_key, model, f"{width}x{height}", timeout)
        return generate_image_pollinations(prompt, base_url, api_key, model, width, height, seed, timeout)
    else:
        raise ImageGenError(f"Unknown image provider: {provider}")
