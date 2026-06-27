#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Web Server - Local web UI for AIdex
Apache 2.0 License

A zero-dependency HTTP server (stdlib http.server only) that serves the
AIdex web UI and bridges it to the existing Agent/Config/provider code —
no logic is duplicated in JavaScript. Runs entirely on localhost by
default; nothing is exposed to the network unless explicitly requested.

Endpoints:
  GET  /                       -> index.html (the SPA)
  GET  /static/<file>          -> static assets (css/js)
  GET  /api/status             -> current provider/model/workspace/safe_mode
  GET  /api/models?provider=X  -> live model list (same engine as the TUI)
  POST /api/models/switch      -> {model} set current model
  POST /api/provider/switch    -> {provider} set current provider
  GET  /api/config             -> non-secret config (keys masked)
  POST /api/config             -> update config (provider keys, workspace, etc.)
  GET  /api/history             -> conversation history
  POST /api/history/clear      -> clear conversation
  POST /api/chat (SSE)         -> {message} streams the agent's response
  GET  /api/tools              -> list of available tools
  POST /api/tool (sync)        -> {tool, params} run a tool directly (used by file browser etc.)
  GET  /api/fs/list?path=      -> directory listing for the in-browser file browser
  GET  /api/fs/read?path=      -> file content for the in-browser file viewer/editor
  POST /api/fs/write           -> {path, content} save a file from the editor
  GET  /api/image-providers    -> available image-generation backends
  POST /api/image               -> {prompt, width?, height?, seed?} generate an image,
                                    returns it inline as base64 (free by default, no key needed)
"""

from __future__ import annotations
import os
import sys
import json
import time
import base64
import threading
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    # Python < 3.7 doesn't have ThreadingHTTPServer; build the equivalent.
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import config, PROVIDERS, IMAGE_PROVIDERS  # noqa: E402
from src.core.agent import agent, normalize_message_content  # noqa: E402
from src.core.imagegen import ImageGenError  # noqa: E402
from src.tools.file_tools import TOOL_DEFINITIONS, list_directory_flat, read_file_raw, write_file  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _safe_static_path(rel_path: str):
    """Resolve a requested static path safely inside STATIC_DIR (no
    directory traversal, regardless of platform path separators)."""
    rel_path = rel_path.lstrip("/")
    full = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
    if not full.startswith(os.path.normpath(STATIC_DIR)):
        return None
    return full


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _is_within_workspace(path: str, workspace: str) -> bool:
    """True if `path` (absolute or relative) resolves to somewhere inside
    `workspace`. Used to confine the web UI's file browser and direct
    tool-execution endpoint to the configured workspace, since a
    browser-reachable HTTP API is a fundamentally different trust boundary
    than a local terminal session — the CLI agent's broader path handling
    is intentional for a developer with local shell access already; the
    web surface should not inherit that by default."""
    ws_abs = os.path.realpath(os.path.abspath(workspace))
    target = path if os.path.isabs(path) else os.path.join(ws_abs, path)
    target_abs = os.path.realpath(os.path.abspath(target))
    return target_abs == ws_abs or target_abs.startswith(ws_abs + os.sep)


# Tools that execute arbitrary shell/Python code. These are far more
# dangerous to expose over HTTP than file read/write, so the web UI's
# direct tool-execution endpoint blocks them by default; enable explicitly
# via config if you understand the risk (e.g. a fully trusted, localhost
# only, single-user setup).
_SHELL_TOOLS = {"run_command", "run_python"}

# RalphState/RalphRunner live at module level (not per-Handler-instance,
# since http.server creates a fresh Handler for every request) so a task
# list and an in-progress run persist across the separate HTTP requests
# that add tasks, start a run, and stop it.
_ralph_state = None
_ralph_runner = None
_ralph_lock = threading.Lock()


def _get_ralph_state():
    global _ralph_state
    if _ralph_state is None:
        from src.core.ralph import RalphState, default_tasks_path
        _ralph_state = RalphState(default_tasks_path(config.workspace))
        _ralph_state.load()
    return _ralph_state


class Handler(BaseHTTPRequestHandler):
    server_version = "AIdex/1.3"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep terminal clean; the TUI banner already prints the URL

    # ---- helpers ---------------------------------------------------------

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _send_file(self, path):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404, "Not found")
            return
        ext = os.path.splitext(path)[1]
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- routing -----------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"))
        elif path.startswith("/static/"):
            full = _safe_static_path(path[len("/static/"):])
            if full and os.path.isfile(full):
                self._send_file(full)
            else:
                self.send_error(404, "Not found")
        elif path == "/api/status":
            self._api_status()
        elif path == "/api/models":
            self._api_models(qs)
        elif path == "/api/config":
            self._api_get_config()
        elif path == "/api/history":
            self._api_history()
        elif path == "/api/tools":
            self._api_tools()
        elif path == "/api/fs/list":
            self._api_fs_list(qs)
        elif path == "/api/fs/read":
            self._api_fs_read(qs)
        elif path == "/api/image-providers":
            self._api_image_providers()
        elif path == "/api/ralph":
            self._api_ralph_status()
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/chat":
            self._api_chat_stream()
        elif path == "/api/models/switch":
            self._api_switch_model()
        elif path == "/api/provider/switch":
            self._api_switch_provider()
        elif path == "/api/config":
            self._api_set_config()
        elif path == "/api/history/clear":
            self._read_json_body()  # drain the body — see _api_ralph_clear's comment
            agent.clear_history()
            self._send_json({"ok": True})
        elif path == "/api/tool":
            self._api_run_tool()
        elif path == "/api/fs/write":
            self._api_fs_write()
        elif path == "/api/image":
            self._api_generate_image()
        elif path == "/api/ralph/add":
            self._api_ralph_add()
        elif path == "/api/ralph/run":
            self._api_ralph_run_stream()
        elif path == "/api/ralph/stop":
            self._api_ralph_stop()
        elif path == "/api/ralph/clear":
            self._api_ralph_clear()
        else:
            self.send_error(404, "Not found")

    # ---- handlers ----------------------------------------------------------

    def _api_status(self):
        info = config.get_provider_info()
        self._send_json({
            "provider": config.provider,
            "provider_name": info.get("name", config.provider),
            "model": config.model,
            "workspace": config.workspace,
            "safe_mode": bool(config.get("safe_mode", True)),
            "has_key": config.has_usable_key(),
            "message_count": len(agent.messages),
            "providers": list(PROVIDERS.keys()),
        })

    def _api_models(self, qs):
        provider = (qs.get("provider") or [None])[0]
        refresh = (qs.get("refresh") or ["0"])[0] == "1"
        try:
            models, source = config.get_live_models(provider, force_refresh=refresh)
            self._send_json({
                "source": source,
                "current": config.model,
                "models": [
                    {
                        "id": m.id, "name": m.name, "context_length": m.context_length,
                        "context_label": m.context_label(), "price_label": m.price_label(),
                        "is_free": m.is_free, "supports_tools": m.supports_tools,
                    }
                    for m in models
                ],
            })
        except Exception as e:
            self._send_json({"error": str(e), "models": [], "source": "error"}, status=200)

    def _api_switch_model(self):
        data = self._read_json_body()
        model = data.get("model", "")
        if not model:
            self._send_json({"error": "model required"}, status=400)
            return
        config.set("model", model)
        self._send_json({"ok": True, "model": model})

    def _api_switch_provider(self):
        data = self._read_json_body()
        provider = data.get("provider", "")
        if provider not in PROVIDERS:
            self._send_json({"error": "unknown provider"}, status=400)
            return
        config.set("provider", provider)
        try:
            models, _src = config.get_live_models(provider)
            free = [m for m in models if m.is_free]
            pick = (free[0] if free else models[0]) if models else None
            if pick:
                config.set("model", pick.id)
        except Exception:
            static = config.all_models(provider)
            if static:
                config.set("model", static[0])
        self._send_json({"ok": True, "provider": provider, "model": config.model})

    def _api_get_config(self):
        data = config.as_dict()
        for p, info in PROVIDERS.items():
            field = info.get("key_field")
            if field and field in data:
                data[field] = _mask_key(data[field])
        self._send_json(data)

    def _api_set_config(self):
        data = self._read_json_body()
        # Only allow known, safe keys to be set from the web UI.
        allowed = {
            "workspace", "safe_mode", "max_tokens", "temperature", "stream",
            "request_timeout", "max_retries", "ollama_base_url",
        }
        key_fields = {info["key_field"] for info in PROVIDERS.values() if info.get("key_field")}
        for k, v in data.items():
            if k in allowed or k in key_fields:
                if k == "workspace" and not os.path.isdir(v):
                    continue
                config.set(k, v)
        self._send_json({"ok": True})

    def _api_history(self):
        msgs = []
        for m in agent.get_history():
            msgs.append({"role": m.get("role", "?"), "content": normalize_message_content(m)})
        self._send_json({"messages": msgs})

    def _api_tools(self):
        self._send_json({"tools": TOOL_DEFINITIONS})

    def _api_fs_list(self, qs):
        path = (qs.get("path") or ["."])[0]
        if not _is_within_workspace(path, config.workspace):
            self._send_json({"ok": False, "error": "Path is outside the workspace", "path": path, "items": []}, status=403)
            return
        result, items = list_directory_flat(path, config.workspace)
        self._send_json({"ok": result.success, "error": result.error, "path": path, "items": items})

    def _api_fs_read(self, qs):
        path = (qs.get("path") or [""])[0]
        if not _is_within_workspace(path, config.workspace):
            self._send_json({"ok": False, "output": "", "error": "Path is outside the workspace"}, status=403)
            return
        result = read_file_raw(path, config.workspace)
        self._send_json({"ok": result.success, "output": result.output, "error": result.error})

    def _api_fs_write(self):
        data = self._read_json_body()
        path = data.get("path", "")
        content = data.get("content", "")
        if not _is_within_workspace(path, config.workspace):
            self._send_json({"ok": False, "output": "", "error": "Path is outside the workspace"}, status=403)
            return
        result = write_file(path, content, config.workspace)
        self._send_json({"ok": result.success, "output": result.output, "error": result.error})

    def _api_image_providers(self):
        self._send_json({
            "current": config.get("image_provider", "pollinations"),
            "providers": [
                {"id": pid, "name": info["name"], "requires_key": info.get("requires_key", True),
                 "models": info.get("models", [])}
                for pid, info in IMAGE_PROVIDERS.items()
            ],
        })

    def _api_generate_image(self):
        data = self._read_json_body()
        prompt = data.get("prompt", "")
        if not prompt:
            self._send_json({"ok": False, "error": "prompt is required"}, status=400)
            return
        width = int(data.get("width", 1024))
        height = int(data.get("height", 1024))
        seed = data.get("seed")
        save_as = data.get("save_as", "")

        if save_as and not _is_within_workspace(save_as, config.workspace):
            self._send_json({"ok": False, "error": "Path is outside the workspace"}, status=403)
            return

        try:
            result = config.generate_image(prompt, width=width, height=height, seed=seed)
        except ImageGenError as e:
            self._send_json({"ok": False, "error": str(e)}, status=502)
            return
        except Exception as e:
            self._send_json({"ok": False, "error": f"Unexpected error: {e}"}, status=500)
            return

        saved_path = None
        if save_as:
            full = os.path.join(config.workspace, save_as) if not os.path.isabs(save_as) else save_as
            try:
                os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
                with open(full, "wb") as f:
                    f.write(result.data)
                saved_path = save_as
            except OSError as e:
                self._send_json({"ok": False, "error": f"Generated but failed to save: {e}"}, status=500)
                return

        self._send_json({
            "ok": True,
            "image_base64": base64.b64encode(result.data).decode("ascii"),
            "content_type": result.content_type,
            "filename": result.suggested_filename(),
            "saved_path": saved_path,
        })

    def _api_ralph_status(self):
        state = _get_ralph_state()
        self._send_json({
            "tasks": [t.to_dict() for t in state.tasks],
            "counts": state.counts(),
            "iteration": state.iteration,
            "paused": state.paused,
            "running": _ralph_runner is not None,
            "tasks_path": state.tasks_path,
        })

    def _api_ralph_add(self):
        data = self._read_json_body()
        title = data.get("title", "").strip()
        if not title:
            self._send_json({"ok": False, "error": "title is required"}, status=400)
            return
        state = _get_ralph_state()
        task = state.add_task(title)
        state.save()
        self._send_json({"ok": True, "task": task.to_dict()})

    def _api_ralph_clear(self):
        global _ralph_runner
        self._read_json_body()  # drain the request body even though unused —
        # otherwise leftover bytes sit in the socket buffer and corrupt the
        # next request's parsing on this reused HTTP/1.1 connection (this
        # was a real, confirmed bug: a stray "{}" prefixed onto the
        # following request line caused a spurious 501).
        if _ralph_runner is not None:
            self._send_json({"ok": False, "error": "Cannot clear while a run is in progress — stop it first"}, status=409)
            return
        state = _get_ralph_state()
        state.tasks = []
        state.iteration = 0
        state.save()
        self._send_json({"ok": True})

    def _api_ralph_stop(self):
        global _ralph_runner
        self._read_json_body()  # drain the body — see _api_ralph_clear's comment
        with _ralph_lock:
            if _ralph_runner is not None:
                _ralph_runner.request_stop()
                self._send_json({"ok": True, "message": "Stop requested — will stop after the current task."})
            else:
                self._send_json({"ok": True, "message": "No run in progress."})

    def _api_ralph_run_stream(self):
        """SSE stream of an autonomous Ralph run, mirroring /api/chat's
        event shape (text/tool_call/tool_result/error) plus Ralph-specific
        events (task_start, task_done, finished) so the frontend can render
        per-task progress without a different protocol to learn."""
        global _ralph_runner
        from src.core.ralph import RalphRunner, DEFAULT_MAX_ITERATIONS

        data = self._read_json_body()
        max_iterations = int(data.get("max_iterations", DEFAULT_MAX_ITERATIONS))

        with _ralph_lock:
            if _ralph_runner is not None:
                self._send_json({"error": "A Ralph run is already in progress"}, status=409)
                return
            state = _get_ralph_state()
            # confine_to_workspace mirrors the same gating /api/chat uses —
            # an autonomous loop calling tools unattended is exactly the
            # case that protection exists for, even more so than a single
            # chat turn a person is watching live.
            excluded = set() if config.get("web_allow_shell_tools", False) else _SHELL_TOOLS
            runner = RalphRunner(agent, state, max_iterations=max_iterations,
                                  excluded_tools=excluded, confine_to_workspace=True)
            _ralph_runner = runner

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        # Deliberately close rather than keep-alive: this handler streams
        # an unknown number of bytes with no Content-Length and no chunked
        # transfer-encoding, so the only framing-safe way to tell the
        # client (and this stdlib HTTP/1.1 persistent-connection server)
        # the response is actually finished is to close the connection.
        # Claiming keep-alive here was a real bug: the next request reused
        # on the same socket would arrive while the previous response's
        # framing was still ambiguous, corrupting it (manifested as a
        # browser-side "Unsupported method" 501 on the very next fetch).
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True

        def emit(event_type, payload):
            try:
                chunk = "event: %s\ndata: %s\n\n" % (event_type, json.dumps(payload))
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                raise StopIteration

        def on_task_start(task, index, total):
            emit("task_start", {"task": task.to_dict(), "index": index, "total": total})

        def on_task_event(task, etype, content):
            if etype == "text":
                emit("text", {"text": content})
            elif etype == "tool_call":
                emit("tool_call", {"name": content})
            elif etype == "tool_result":
                emit("tool_result", {"output": content})
            elif etype == "error":
                emit("error", {"message": content})

        def on_task_done(task, outcome):
            emit("task_done", {"task": task.to_dict(), "outcome": outcome})

        def on_finished(reason):
            emit("finished", {"reason": reason})

        try:
            runner.run(on_task_start=on_task_start, on_task_event=on_task_event,
                       on_task_done=on_task_done, on_finished=on_finished)
        except StopIteration:
            pass
        except Exception as e:
            try:
                emit("error", {"message": "Unexpected server error: %s" % e})
            except StopIteration:
                pass
        finally:
            with _ralph_lock:
                _ralph_runner = None

    def _api_run_tool(self):
        data = self._read_json_body()
        tool_name = data.get("tool", "")
        params = data.get("params", {})
        if tool_name in _SHELL_TOOLS and not config.get("web_allow_shell_tools", False):
            self._send_json({
                "ok": False, "output": "",
                "error": "Shell/Python execution is disabled for the web UI by default. "
                         "Enable 'web_allow_shell_tools' in config if you understand the risk.",
            }, status=403)
            return
        # Any tool param that looks like a workspace-relative path must stay
        # inside the workspace when invoked from the web UI.
        for key in ("path", "file", "directory", "output_path"):
            if key in params and isinstance(params[key], str) and not _is_within_workspace(params[key], config.workspace):
                self._send_json({"ok": False, "output": "", "error": "Path is outside the workspace"}, status=403)
                return
        result = agent.run_tool(tool_name, params)
        self._send_json({"ok": result.success, "output": result.output, "error": result.error})

    def _api_chat_stream(self):
        """Server-Sent Events stream of the agent's response."""
        data = self._read_json_body()
        user_input = data.get("message", "")
        if not user_input:
            self._send_json({"error": "message required"}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        # Deliberately close rather than keep-alive — same fix and same
        # reasoning as _api_ralph_run_stream: an unbounded streamed
        # response with no Content-Length/chunked-encoding is ambiguously
        # framed under HTTP/1.1 keep-alive, and the next request reused on
        # the same connection can arrive corrupted. See that method's
        # comment for the full explanation; this endpoint had the exact
        # same bug.
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True

        def emit(event_type, payload):
            try:
                chunk = "event: %s\ndata: %s\n\n" % (event_type, json.dumps(payload))
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                raise StopIteration

        try:
            excluded = set() if config.get("web_allow_shell_tools", False) else _SHELL_TOOLS
            for typ, content in agent.chat_stream(user_input, excluded_tools=excluded, confine_to_workspace=True):
                if typ == "text":
                    emit("text", {"text": content})
                elif typ == "tool_call":
                    emit("tool_call", {"name": content})
                elif typ == "tool_result":
                    emit("tool_result", {"output": content})
                elif typ == "error":
                    emit("error", {"message": content})
                elif typ == "done":
                    emit("done", {})
        except StopIteration:
            pass
        except Exception as e:
            try:
                emit("error", {"message": "Unexpected server error: %s" % e})
            except StopIteration:
                pass


def _find_free_port(preferred=8420):
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0  # let the OS pick


def run_web_server(host="127.0.0.1", port=None, open_browser=True):
    if port is None:
        port = _find_free_port()
    server = ThreadingHTTPServer((host, port), Handler)
    url = "http://%s:%d" % (host, port)
    print("AIdex web UI running at %s" % url)
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_web_server()
