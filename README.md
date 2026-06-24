# AIdex AI Coding Agent

```
   ___    ____    __
  / _ |  /  _/___/ /__ __
 / __ | _/ // _  / -_) \ /
/_/ |_|/___/\_,_/\__/_\_\

   Professional CLI AI Coding Agent v1.1.0
```

> Formerly known as **Nexus**. Renamed to **AIdex**. Old `nexus.py` /
> `nexus`/`nexus.bat` launchers and config still work — see Migration below.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-2.7%2B%20%2F%203.6%2B-green.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**AIdex** is a fully-featured, professional CLI AI coding agent that runs in your terminal. It connects to multiple AI providers with free and paid models, and can actually create, edit, delete files, run commands, manage git, and more — just like professional AI coding tools.

AIdex is built to run **everywhere** — from a fresh Windows 11 64-bit machine down to a 32-bit Windows XP box, an old Linux netbook, or a Raspberry Pi. When the enhanced terminal UI's dependencies aren't available, AIdex automatically drops into a zero-dependency plain-text interface with the exact same features, so it never just refuses to start.

---

## ✨ Features

- 🤖 **Multi-Provider**: OpenRouter (100+ models), Groq (ultra-fast, free), Anthropic, OpenAI, **Ollama (fully local/offline, no API key)**
- 🆓 **Free Models**: Many free models via OpenRouter and Groq — no credit card needed
- 📁 **File Operations**: Read, write, edit, delete, move, copy files
- 🖊️ **Smart Editing**: `str_replace`-style edits with diff preview
- 🖥️ **Shell Commands**: Execute any shell command in your workspace
- 🐍 **Python Execution**: Run Python code snippets inline
- 🔀 **Git Integration**: status, diff, log, add, commit, init
- 🔍 **Search**: Find files by name or content (grep)
- 📊 **Project Analysis**: Detect project type, file stats
- 🎨 **Rich TUI**: Beautiful terminal UI with syntax highlighting
- ⌨️ **Auto-complete**: Command completion with history
- 💾 **Session Save/Load**: Save and restore conversations
- 🔒 **Safe Mode**: Blocks dangerous commands by default
- 🌐 **Cross-Platform**: Windows XP/Vista/7/8/10/11, Linux, macOS, 32/64-bit
- 🪶 **Zero-Dependency Fallback**: Automatic plain-text UI when Rich/prompt_toolkit aren't available
- 🐢 **Low-End Friendly**: Memory-bounded file tools (`tail_file`, `head_file`, `read_file_lines`) for huge files on limited RAM
- 🔌 **Offline Mode**: Use Ollama for a fully local AI with no internet connection
- 🔁 **Auto-Retry**: Network requests retry with backoff on transient failures

---

## 🚀 Quick Start

### Requirements
- Python 2.7+ or 3.x (full enhanced UI needs Python 3.7+; plain UI works on 2.7+)
- Works on Windows XP through Windows 11, Linux, macOS, 32-bit and 64-bit

### Installation

```bash
# Clone or download
git clone https://github.com/Zelvior/AIdex
cd AIdex

# Run the installer (handles dependencies where possible, never hard-fails)
python install.py

# Start AIdex
python aidex.py
```

### Windows
```cmd
python install.py
aidex.bat
```

### Linux/macOS
```bash
python3 install.py
./aidex
# or
python3 aidex.py
```

### Forcing a specific interface
```bash
python aidex.py --plain   # zero-dependency text UI (XP, 32-bit, minimal Python)
python aidex.py --full    # Rich/prompt_toolkit UI (requires those packages)
```

---

## 🔑 API Keys (Free Options!)

You do **not** need a paid API key to use AIdex. OpenRouter, Groq, and Ollama all offer free options:

| Provider | Free Models | Speed | Get Key |
|----------|-------------|-------|---------|
| **OpenRouter** | ✅ Many free | Normal | [openrouter.ai](https://openrouter.ai) |
| **Groq** | ✅ Yes (all!) | ⚡ Very fast | [console.groq.com](https://console.groq.com) |
| **Ollama** | ✅ Yes (all, local) | Depends on hardware | [ollama.com](https://ollama.com) — no key needed |
| Anthropic | ❌ | Fast | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | ❌ | Fast | [platform.openai.com](https://platform.openai.com) |

After starting AIdex, type `/config` to enter your API key. Ollama runs
fully on your own machine — ideal for low-end or offline devices, no
internet or account required (install Ollama separately, then point
AIdex at it).

---

## 💬 Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/config` | Configure API key, provider, model, workspace |
| `/provider <name>` | Switch provider (openrouter/groq/anthropic/openai/ollama) |
| `/model <name>` | Switch AI model |
| `/models` | List available models |
| `/workspace <path>` | Set working directory |
| `/clear` | Clear conversation history |
| `/save [file]` | Save conversation to JSON |
| `/load <file>` | Load saved conversation |
| `/status` | Show current config |
| `/tools` | List all available tools |
| `/run <cmd>` | Run shell command directly |
| `/read <file>` | Read file directly |
| `/ls [path]` | List directory |
| `/analyze` | Analyze project structure |
| `/safemode` | Toggle safe mode |
| `/docs` | Show documentation |
| `/credits` | Show credits |
| `/terms` | Terms and conditions |
| `/privacy` | Privacy policy |
| `/license` | Apache 2.0 license |
| `/disk [path]` | Show disk usage and directory size |
| `/env` | Show Python/OS/architecture info |
| `/which <name>` | Locate an executable on PATH |
| `/exit` | Exit AIdex |

---

## 🛠️ Available Tools

The AI automatically calls these tools to perform real actions:

| Tool | Description |
|------|-------------|
| `read_file` | Read file with line numbers |
| `write_file` | Create or overwrite file |
| `edit_file` | Replace specific text (str_replace) |
| `patch_lines` | Replace line range |
| `append_file` | Append to file |
| `delete_file` | Delete file/directory |
| `move_file` | Move/rename |
| `copy_file` | Copy file |
| `create_directory` | Create directories |
| `list_directory` | List directory tree |
| `search_files` | Find files by name/content |
| `grep_file` | Search inside file |
| `run_command` | Execute shell command |
| `run_python` | Execute Python code |
| `git_status` | Git status |
| `git_diff` | Git diff |
| `git_log` | Git history |
| `git_add` | Stage files |
| `git_commit` | Commit changes |
| `git_init` | Init repository |
| `analyze_project` | Project structure analysis |
| `get_file_info` | File metadata |
| `read_file_lines` | Read a specific line range (memory-efficient) |
| `head_file` | Read first N lines |
| `tail_file` | Read last N lines (memory-bounded, huge-file safe) |
| `count_lines` | Count lines/words/chars in a file |
| `disk_usage` | Disk free/used/total + directory size |
| `env_info` | Python/OS/CPU architecture report |
| `find_replace_in_files` | Bulk find/replace across files (dry-run by default) |
| `git_branch` | List git branches |
| `git_checkout` | Switch/create git branch |
| `which` | Locate an executable on PATH |

---

## 💡 Example Prompts

```
> Create a Python Flask REST API with CRUD operations for a todo list

> Read main.py and fix any bugs you find

> Analyze this project and suggest improvements

> Create a Dockerfile for this Python application

> Write unit tests for all functions in utils.py, then run them

> Refactor this JavaScript code to use modern ES6+ features

> Set up a basic Next.js project structure

> Find all TODO comments in the codebase

> Create a .gitignore file for a Python project

> Read package.json and update all dependencies to latest versions
```

---

## 📁 Project Structure

```
aidex/
├── aidex.py              ← Main entry point (auto-detects UI)
├── nexus.py              ← Legacy alias, forwards to aidex.py
├── install.py            ← Universal installer (never hard-fails)
├── setup.py              ← pip install support
├── README.md
├── LICENSE
├── CHANGELOG.md
└── src/
    ├── core/
    │   ├── agent.py      ← AI agent orchestrator
    │   └── config.py     ← Configuration manager
    ├── providers/
    │   └── base.py       ← OpenRouter, Groq, Anthropic, OpenAI, Ollama
    ├── tools/
    │   └── file_tools.py ← All file/shell/git tools
    └── tui/
        ├── app.py        ← Enhanced UI (Rich + prompt_toolkit)
        └── plain.py      ← Zero-dependency fallback UI (Python 2.7+)
```

---

## 🔒 Safe Mode

Safe mode (enabled by default) blocks destructive commands like `rm -rf /`.
Toggle with `/safemode`. When OFF, all commands execute without restriction.

---

## ⚙️ Configuration

Config stored at:
- **Windows**: `%APPDATA%\aidex\config.json`
- **macOS**: `~/Library/Application Support/aidex/config.json`
- **Linux**: `~/.config/aidex/config.json`

### Migrating from Nexus
If you previously used Nexus, AIdex automatically migrates your old
`nexus-agent` config (provider, API keys, model, settings) into the
new `aidex` location the first time it runs — nothing is lost, no
action needed.

---

## 🌍 Compatibility

| OS | Version | 32-bit | 64-bit | Interface |
|----|---------|--------|--------|-----------|
| Windows | XP, Vista, 7, 8, 10, 11 | ✅ | ✅ | Plain (XP/old) → Full (7+) |
| Linux | Any (Ubuntu, Debian, Fedora, Arch…) | ✅ | ✅ | Full (or Plain if deps missing) |
| macOS | 10.9+ | ✅ | ✅ | Full (or Plain if deps missing) |

The enhanced Rich/prompt_toolkit interface needs Python 3.7+. On
anything older — including Windows XP and many 32-bit-only Python
installs — AIdex automatically uses its built-in plain-text interface,
which needs **no third-party packages at all** and supports Python
2.7+. You get the exact same commands and tools either way.

---

## 📄 License

Apache License 2.0 — See [LICENSE](LICENSE) file.

Copyright 2024-2026 AIdex Contributors (originally Nexus AI Coding Agent)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 🔗 Links

- [OpenRouter (free models)](https://openrouter.ai)
- [Groq (free, fast)](https://console.groq.com)
- [Ollama (free, local, offline)](https://ollama.com)
- [Report Issues](https://github.com/Zelvior/AIdex/issues)
