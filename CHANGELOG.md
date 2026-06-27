# Changelog

All notable changes to AIdex AI Coding Agent (formerly Nexus) will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.3.0] - 2026-06-27

### Added
- `BRAIN.md` — a dense, single-file project-context document (architecture, the three shared-engine front ends, tool system, live model fallback chain, web security model, web API reference, compatibility constraints, and known design decisions). Intended to be read first instead of re-reading the whole codebase when picking the project back up.
- **Free image generation, no API key needed by default** — new `generate_image` tool backed by Pollinations (free, no signup), available as a native function-calling tool, an `/image <prompt>` command in both TUIs, and a `POST /api/image` endpoint on the web (returns base64, with an optional `save_as`). Configured independently from the chat provider via `image_provider`/`image_model`.
- **Two new chat providers**: `pollinations` (free, no key, now the **zero-config default** — a fresh install can chat AND generate images with no setup) and `gemini` (Google's OpenAI-compatible endpoint).
- **`custom` provider** (chat) and **`custom` image backend** — point AIdex at any other OpenAI-compatible chat API or image API by supplying a base URL (and optional key) in config.
- **Ralph TUI** — an autonomous task-loop orchestrator (`src/core/ralph.py`): add tasks, then run them one at a time with the agent until the list is empty, a safety cap is hit, or you stop it. Crash-safe JSON state persistence (atomic write+rename), resumable. Available via `/ralph`, `/ralph add <title>`, `/ralph run [max_iterations]`, `/ralph clear` in both TUIs, and a dedicated panel in the web UI (`GET/POST /api/ralph*`, SSE run stream). Pure stdlib, Python 2.7-compatible — runs under the plain TUI on Windows XP / 32-bit exactly like everything else there.
- `config.needs_api_key()` / `config.has_usable_key()` — proper "is this provider ready to use" checks that correctly distinguish "no key required" (Pollinations, Ollama) from "key genuinely missing."

### Fixed
- **Real, exploitable bug**: several places (`agent.py`'s `_get_provider`, both TUIs' status displays, the web `/api/status`) used to treat `get_api_key()`'s truthy "not needed" sentinel as if a real key were configured. Fixed by switching every call site to the new `has_usable_key()`.
- **Real, exploitable bug**: a tool's `output_path`-style parameter (e.g. `generate_image`) could write outside the configured workspace when invoked through web chat, even though direct file-browser endpoints were already confined — the AI deciding to pass an absolute path mid-conversation bypassed the per-endpoint checks entirely. Fixed with a second confinement layer inside `Agent._execute_tool()` itself (`confine_to_workspace`), threaded through `chat_stream()` and `RalphRunner`, so it covers every current and future file-writing tool regardless of which UI surface triggered it.
- **Real bug**: two SSE streaming endpoints (`/api/chat`, `/api/ralph/run`) claimed `Connection: keep-alive` while sending an unbounded response with no `Content-Length`/chunked-encoding — ambiguous framing under HTTP/1.1 that could corrupt the next request reused on the same connection. Fixed by sending `Connection: close` and setting `close_connection = True`, which is the correct framing for this kind of response.
- **Real bug, more severe in practice**: three POST handlers (`/api/ralph/clear`, `/api/ralph/stop`, the inline `/api/history/clear` branch) never read the request body even when the browser sent one, leaving leftover bytes in the socket buffer that got prepended onto the *next* request line on a reused connection — manifesting as a spurious `501 Unsupported method` on whatever request happened to follow. Only reproducible with genuine HTTP/1.1 connection reuse (a real browser, or Python's `http.client` with an explicit persistent connection) — isolated `curl` calls never showed it. Fixed by draining the body in all three handlers.
- `/help`'s command table was silently swallowing any command containing literal `[brackets]` (e.g. `/disk [path]`, `/ralph run [n]`) because Rich interpreted them as markup tags. Fixed by wrapping cell content in `Text(...)`.
- `run_python` now actually respects the configured safe-mode setting instead of a hardcoded default that ignored it.

## [1.2.0] - 2026-06-26

### Added
- **Web UI** (`python aidex.py --web`): a full browser-based interface served by a zero-dependency local HTTP server (`src/web/server.py`, stdlib `http.server` only — no Flask/Django/extra pip installs). Includes a chat view with streaming responses and live tool-call cards, a file browser/editor, a live model browser with real pricing, and a settings panel. Modern HTML5/CSS (layers, `color-mix()`, container-aware) and vanilla ES modules — no build step.
- **Native function/tool calling**: OpenRouter, Groq, OpenAI, and Ollama now use real OpenAI-style `tools=` function calling instead of asking the model to emit a specific text pattern; Anthropic uses its own native tool format. Both support full multi-turn tool-result loops (the model sees tool output and can react to it). The previous text-pattern parsing is kept as an automatic fallback for models that don't honor native tool calling.
- `read_file_raw()` and `list_directory_flat()` tools: raw, unformatted file/directory access for UI consumption, separate from the AI-facing `read_file`/`list_directory` (which add line numbers and tree formatting not meant to be saved back as file content).
- `list_models` tool so the AI itself can check live pricing/free-tier status when relevant (e.g. "what's a cheaper model for this?").
- Workspace confinement and shell-tool gating for the web UI: absolute paths and `../` traversal outside the configured workspace are rejected (403) on every web file-access endpoint, and `run_command`/`run_python` are excluded from what the web UI's chat offers the model by default (opt in via `web_allow_shell_tools` if you understand the risk).

### Fixed
- **Critical**: `SYSTEM_PROMPT.format()` raised `KeyError` on literal braces in its own example text, crashing the very first turn of every conversation in the original Nexus codebase. Replaced with plain string substitution that can't be broken by future prompt edits.
- `plain.py`'s `/models` command and config wizard were still using the old hardcoded model list instead of live data — now matches the Rich UI's live fetching.
- `AnthropicProvider.list_models()` called a method that didn't exist on its class, silently always returning an empty list; `test_connection()` no longer burns a paid completion just to check a key works.
- `/provider` switch now picks a live free model for the new provider instead of a potentially stale hardcoded one.
- The web file editor no longer corrupts files on save — it previously round-tripped the AI-facing display format (line-number prefixes, file-info header) through the editable text box.
- `run_python` now actually respects the configured safe-mode setting instead of always using a hardcoded default.

## [1.1.0] - 2026-06-25

### Added
- Renamed project from Nexus to **AIdex** (old `nexus.py`/`nexus`/`nexus.bat` kept as working legacy aliases)
- New `aidex.py` entry point with automatic interface detection
- Zero-dependency **plain-text fallback UI** (`src/tui/plain.py`), pure stdlib, works on Python 2.7+ — used automatically when Rich/prompt_toolkit are unavailable or fail
- `--plain` and `--full` flags to force a specific interface
- **Ollama provider** support — fully local/offline AI models, no API key or internet required, ideal for low-end or air-gapped devices
- Automatic one-time migration of old `nexus-agent` config into the new `aidex` config location
- Network request retry with exponential backoff for transient failures; configurable timeout and retry count
- 11 new tools: `read_file_lines`, `head_file`, `tail_file` (memory-bounded for huge files), `count_lines`, `disk_usage`, `env_info`, `find_replace_in_files` (dry-run by default), `git_branch`, `git_checkout`, `which`
- New slash commands: `/disk`, `/env`, `/which`
- Installer no longer hard-exits on old Python versions; degrades gracefully and explains plain-mode fallback
- Explicit Windows XP / 32-bit compatibility notes throughout documentation

### Changed
- Config directory moved from `nexus-agent` to `aidex` (with automatic migration)
- Default config now includes `low_end_mode`, `plain_ui`, `request_timeout`, `max_retries` settings
- README, credits, terms, privacy, and license text rebranded to AIdex while preserving all original content and disclosures

### Compatibility
- No existing functionality was removed. All original Nexus tools, commands, and providers continue to work unchanged.

## [1.0.0] - 2024-01-01

### Added
- Initial release
- Multi-provider support: OpenRouter, Groq, Anthropic, OpenAI
- 22 built-in tools: file ops, shell, git, search, project analysis
- Rich TUI with syntax highlighting and streaming responses
- Cross-platform support: Windows 7+, Linux, macOS (32/64-bit)
- Safe mode to block dangerous commands
- Session save/load (JSON)
- Auto-complete for slash commands
- Config wizard (`/config`)
- Free model support via OpenRouter and Groq
- Apache 2.0 license
- Full documentation, credits, terms, privacy policy
- Universal installer (`install.py`)
