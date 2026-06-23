# Nexus AI Coding Agent

```
  _   _                      _    ___
 | \ | | _____  ___   _ ___ | |  / _ \
 |  \| |/ _ \ \/ / | | / __|| | | (_) |
 | |\  |  __/>  <| |_| \__ \| |__\__, |
 |_| \_|\___/_/\_\\__,_|___/|____|  /_/

   Professional CLI AI Coding Agent v1.0.0
```

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-green.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**Nexus** is a fully-featured, professional CLI AI coding agent that runs in your terminal. It connects to multiple AI providers with free and paid models, and can actually create, edit, delete files, run commands, manage git, and more — just like professional AI coding tools.

---

## ✨ Features

- 🤖 **Multi-Provider**: OpenRouter (100+ models), Groq (ultra-fast, free), Anthropic, OpenAI
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
- 🌐 **Cross-Platform**: Windows 7+, Linux, macOS, 32/64-bit

---

## 🚀 Quick Start

### Requirements
- Python 3.6+ (works on 32-bit and 64-bit)
- Works on Windows 7/8/10/11, Linux, macOS

### Installation

```bash
# Clone or download
git clone https://github.com/nexus-agent/nexus
cd nexus

# Run the installer (handles all dependencies)
python install.py

# Start Nexus
python nexus.py
```

### Windows
```cmd
python install.py
nexus.bat
```

### Linux/macOS
```bash
python3 install.py
./nexus
# or
python3 nexus.py
```

---

## 🔑 API Keys (Free Options!)

You do **not** need a paid API key to use Nexus. Both OpenRouter and Groq offer free tiers:

| Provider | Free Models | Speed | Get Key |
|----------|-------------|-------|---------|
| **OpenRouter** | ✅ Many free | Normal | [openrouter.ai](https://openrouter.ai) |
| **Groq** | ✅ Yes (all!) | ⚡ Very fast | [console.groq.com](https://console.groq.com) |
| Anthropic | ❌ | Fast | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | ❌ | Fast | [platform.openai.com](https://platform.openai.com) |

After starting Nexus, type `/config` to enter your API key.

---

## 💬 Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/config` | Configure API key, provider, model, workspace |
| `/provider <name>` | Switch provider (openrouter/groq/anthropic/openai) |
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
| `/exit` | Exit Nexus |

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
nexus-agent/
├── nexus.py              ← Main entry point
├── install.py            ← Universal installer
├── setup.py              ← pip install support
├── README.md
├── LICENSE
├── CHANGELOG.md
└── src/
    ├── core/
    │   ├── agent.py      ← AI agent orchestrator
    │   └── config.py     ← Configuration manager
    ├── providers/
    │   └── base.py       ← OpenRouter, Groq, Anthropic, OpenAI
    ├── tools/
    │   └── file_tools.py ← All file/shell/git tools
    └── tui/
        └── app.py        ← Terminal UI (Rich + prompt_toolkit)
```

---

## 🔒 Safe Mode

Safe mode (enabled by default) blocks destructive commands like `rm -rf /`.
Toggle with `/safemode`. When OFF, all commands execute without restriction.

---

## ⚙️ Configuration

Config stored at:
- **Windows**: `%APPDATA%\nexus-agent\config.json`
- **macOS**: `~/Library/Application Support/nexus-agent/config.json`
- **Linux**: `~/.config/nexus-agent/config.json`

---

## 🌍 Compatibility

| OS | Version | 32-bit | 64-bit |
|----|---------|--------|--------|
| Windows | 7, 8, 10, 11 | ✅ | ✅ |
| Linux | Any (Ubuntu, Debian, Fedora, Arch…) | ✅ | ✅ |
| macOS | 10.9+ | ✅ | ✅ |

Requires Python 3.6+. For older systems, use pyenv or miniconda to get a modern Python.

---

## 📄 License

Apache License 2.0 — See [LICENSE](LICENSE) file.

Copyright 2024 Nexus Contributors

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
- [Report Issues](https://github.com/nexus-agent/issues)
