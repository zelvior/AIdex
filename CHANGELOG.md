# Changelog

All notable changes to AIdex AI Coding Agent (formerly Nexus) will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- `BRAIN.md` — a dense, single-file project-context document (architecture, the three shared-engine front ends, tool system, live model fallback chain, web security model, web API reference, compatibility constraints, and known design decisions). Intended to be read first instead of re-reading the whole codebase when picking the project back up.

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
