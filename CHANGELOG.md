# Changelog

All notable changes to AIdex AI Coding Agent (formerly Nexus) will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
