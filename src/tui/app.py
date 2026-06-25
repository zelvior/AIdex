#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex TUI - Terminal User Interface using Rich + prompt_toolkit (full mode)
Apache 2.0 License
"""

from __future__ import annotations
import os
import sys
import time
import threading
import platform
from pathlib import Path
from typing import Optional, List

# Rich imports
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.rule import Rule
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns
from rich.align import Align
from rich import box
from rich.style import Style
from rich.theme import Theme

# prompt_toolkit for input
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import WordCompleter

from src.core.config import config, PROVIDERS
from src.core.agent import agent

# ─── THEME ───────────────────────────────────────────────────────────────────

NEXUS_THEME = Theme({
    "banner": "bold cyan",
    "prompt.user": "bold green",
    "prompt.ai": "bold blue",
    "tool.call": "bold yellow",
    "tool.result.ok": "green",
    "tool.result.err": "red",
    "info": "dim white",
    "error": "bold red",
    "success": "bold green",
    "warning": "bold yellow",
    "cmd": "bold magenta",
    "header": "bold white on dark_blue",
})

console = Console(theme=NEXUS_THEME, highlight=False)

# ─── BANNER ──────────────────────────────────────────────────────────────────

BANNER = r"""
   ___    ____    __
  / _ |  /  _/___/ /__ __
 / __ | _/ // _  / -_) \ /
/_/ |_|/___/\_,_/\__/_\_\
"""

VERSION = "1.2.0"


def show_banner():
    console.print(BANNER, style="bold cyan", justify="center")
    console.print(
        Align.center(
            Text(f"AIdex AI Coding Agent v{VERSION}  |  Apache 2.0  |  Type /help for commands", style="dim white")
        )
    )
    console.print()


# ─── COMMANDS ────────────────────────────────────────────────────────────────

COMMANDS = {
    "/help": "Show this help",
    "/config": "Configure API keys and settings",
    "/models": "List live models (try: /models free, /models sort price, /models refresh)",
    "/model <name>": "Switch model (fuzzy-matched against live list)",
    "/provider <name>": "Switch provider (openrouter/groq/anthropic/openai)",
    "/workspace <path>": "Change workspace directory",
    "/clear": "Clear conversation history",
    "/history": "Show conversation history",
    "/save [file]": "Save conversation to file",
    "/load <file>": "Load conversation from file",
    "/status": "Show current status",
    "/tools": "List available tools",
    "/run <cmd>": "Run a shell command directly",
    "/read <file>": "Read a file directly",
    "/ls [path]": "List directory contents",
    "/analyze": "Analyze project structure",
    "/disk [path]": "Show disk usage and directory size",
    "/env": "Show Python/OS/architecture info",
    "/which <name>": "Locate an executable on PATH",
    "/safemode": "Toggle safe mode (blocks dangerous commands)",
    "/docs": "Show documentation",
    "/credits": "Show credits",
    "/terms": "Show terms and conditions",
    "/privacy": "Show privacy policy",
    "/license": "Show Apache 2.0 license info",
    "/exit": "Exit AIdex",
    "/quit": "Exit AIdex",
}

COMMAND_COMPLETER = WordCompleter(list(COMMANDS.keys()), ignore_case=True)

# ─── DISPLAY HELPERS ─────────────────────────────────────────────────────────

def status_bar():
    provider = config.provider
    model = config.model
    ws = config.workspace
    safe = "🔒" if config.get("safe_mode") else "⚠️"
    key_ok = "🔑" if config.get_api_key() else "❌"
    ws_short = ws if len(ws) < 40 else "…" + ws[-37:]

    table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
    table.add_column(style="dim")
    table.add_column(style="bold cyan")
    table.add_column(style="dim")
    table.add_column(style="bold green")
    table.add_column(style="dim")
    table.add_column()
    table.add_row(
        "Provider:", f"{PROVIDERS.get(provider, {}).get('name', provider)}",
        "Model:", model,
        "Workspace:", ws_short,
    )
    info_text = f"  {key_ok} Key  {safe} Safe  msgs:{len(agent.messages)}"
    console.print(Rule(style="dim blue"))
    console.print(table)
    console.print(Text(info_text, style="dim"))
    console.print(Rule(style="dim blue"))


def render_ai_response(text: str):
    """Render AI text, detecting code blocks and formatting them."""
    # Split on code blocks
    parts = text.split("```")
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Regular text — render as markdown if it has markdown-like content
            if part.strip():
                try:
                    console.print(Markdown(part), end="")
                except Exception:
                    console.print(part, end="")
        else:
            # Code block
            lines = part.split("\n", 1)
            lang = lines[0].strip() if lines else ""
            code = lines[1] if len(lines) > 1 else part
            # Skip tool_call blocks (already handled)
            if "<tool_call>" in code or lang == "":
                console.print(part, end="")
            else:
                try:
                    syn = Syntax(code.rstrip(), lang or "text", theme="monokai",
                                 line_numbers=True, word_wrap=True)
                    console.print(Panel(syn, border_style="dim blue", padding=(0, 1)))
                except Exception:
                    console.print(part, end="")


def print_tool_call(name: str, params: dict):
    params_str = ", ".join(f"{k}={repr(v)[:40]}" for k, v in params.items())
    console.print(
        Panel(
            Text(f"⚙ {name}({params_str})", style="bold yellow"),
            border_style="yellow",
            padding=(0, 1),
        )
    )


def print_tool_result(name: str, result):
    style = "green" if result.success else "red"
    icon = "✓" if result.success else "✗"
    output = str(result.output or result.error)
    if len(output) > 2000:
        output = output[:2000] + "\n... [truncated]"
    console.print(
        Panel(
            Text(f"{icon} {name}\n{output}", style=style),
            border_style=style,
            padding=(0, 1),
        )
    )


# ─── SCREENS ─────────────────────────────────────────────────────────────────

def show_help():
    table = Table(title="AIdex Commands", box=box.ROUNDED, border_style="cyan",
                  show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold magenta", width=25)
    table.add_column("Description")
    for cmd, desc in COMMANDS.items():
        table.add_row(cmd, desc)
    console.print(table)


def show_status():
    table = Table(title="AIdex Status", box=box.ROUNDED, border_style="cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value", style="cyan")
    table.add_row("Version", VERSION)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Platform", f"{platform.system()} {platform.machine()}")
    table.add_row("Provider", config.provider)
    table.add_row("Model", config.model)
    table.add_row("API Key", "✓ Set" if config.get_api_key() else "✗ Not set")
    table.add_row("Workspace", config.workspace)
    table.add_row("Safe Mode", "✓ On" if config.get("safe_mode") else "✗ Off")
    table.add_row("Streaming", "✓ On" if config.get("stream") else "✗ Off")
    table.add_row("Max Tokens", str(config.get("max_tokens")))
    table.add_row("Temperature", str(config.get("temperature")))
    table.add_row("Messages in session", str(len(agent.messages)))
    console.print(table)


def show_tools():
    from src.tools.file_tools import TOOL_DEFINITIONS
    table = Table(title="Available Tools", box=box.ROUNDED, border_style="cyan")
    table.add_column("Tool", style="bold magenta", width=22)
    table.add_column("Description")
    table.add_column("Parameters", style="dim", width=30)
    for t in TOOL_DEFINITIONS:
        params = ", ".join(t["parameters"].keys())
        table.add_row(t["name"], t["description"], params)
    console.print(table)


def show_models(query: str = "", sort_by: str = "name", free_only: bool = False, refresh: bool = False):
    from src.core.models import filter_models, sort_models

    provider = config.provider
    info = config.get_provider_info()
    pname = info.get("name", provider)

    with console.status(f"[dim]Fetching live models for {pname}...[/dim]", spinner="dots"):
        models, source = config.get_live_models(force_refresh=refresh)

    shown = sort_models(filter_models(models, query, free_only), sort_by)

    source_label = {
        "live": "[green]● live[/green]",
        "cache": "[cyan]● cached[/cyan]",
        "stale-cache": "[yellow]● cached (stale, refetch failed)[/yellow]",
        "static-fallback": "[red]● built-in fallback (no network/cache)[/red]",
    }.get(source, source)
    age = config.models_cache_age() if source != "live" else "just now"

    title = f"Models — {pname}"
    if query:
        title += f"  (filter: '{query}')"
    table = Table(title=title, box=box.ROUNDED, border_style="cyan")
    table.add_column("", width=2)
    table.add_column("Model", style="cyan", no_wrap=False)
    table.add_column("Context", justify="right", style="dim")
    table.add_column("Price (per 1M tok)", justify="right")
    table.add_column("Tools", justify="center", style="dim")

    for m in shown[:80]:
        mark = "★" if m.id == config.model else " "
        price_style = "green" if m.is_free else "yellow"
        price_text = Text(m.price_label(), style=price_style)
        tools_mark = "✓" if m.supports_tools else ("" if m.supports_tools is None else "✗")
        table.add_row(mark, m.id, m.context_label(), price_text, tools_mark)

    console.print(table)
    console.print(f"★ = current model   |   {len(shown)} of {len(models)} shown   |   source: {source_label} ({age})")
    console.print("[dim]Tip: /models <search>, /models free, /models sort price|context|name, /models refresh[/dim]")


def _parse_models_args(arg: str):
    """Parse '/models <free|refresh|sort X|search terms>' (any combination,
    space separated) into (query, sort_by, free_only, refresh)."""
    tokens = arg.split()
    query_parts = []
    sort_by = "name"
    free_only = False
    refresh = False
    i = 0
    while i < len(tokens):
        t = tokens[i].lower()
        if t == "free":
            free_only = True
        elif t == "refresh":
            refresh = True
        elif t == "sort" and i + 1 < len(tokens):
            sort_by = tokens[i + 1].lower()
            i += 1
        else:
            query_parts.append(tokens[i])
        i += 1
    return " ".join(query_parts), sort_by, free_only, refresh


def _switch_model(arg: str):
    """Switch model with fuzzy matching against the live model list, since
    typing an exact provider-prefixed slug is error-prone."""
    from src.core.models import filter_models
    with console.status("[dim]Checking model...[/dim]", spinner="dots"):
        models, source = config.get_live_models()
    exact = [m for m in models if m.id == arg]
    if exact:
        config.set("model", arg)
        console.print(f"[success]Model set to: {arg}[/success]")
        return
    matches = filter_models(models, arg)
    if len(matches) == 1:
        config.set("model", matches[0].id)
        console.print(f"[success]Model set to: {matches[0].id}[/success] [dim](matched '{arg}')[/dim]")
    elif len(matches) > 1:
        console.print(f"[warning]'{arg}' matches {len(matches)} models — be more specific:[/warning]")
        for m in matches[:15]:
            console.print(f"  {m.id}")
    else:
        # No match in live list — allow setting anyway (e.g. brand-new model
        # not yet reflected in cache), but warn.
        config.set("model", arg)
        console.print(f"[warning]'{arg}' not found in known models for this provider — set anyway.[/warning]")


def show_history():
    from src.core.agent import normalize_message_content
    msgs = agent.get_history()
    if not msgs:
        console.print("[dim]No conversation history.[/dim]")
        return
    for i, msg in enumerate(msgs):
        role = msg.get("role", "?")
        content = normalize_message_content(msg)
        if len(content) > 300:
            content = content[:300] + "…"
        style = "green" if role == "user" else ("magenta" if role == "tool" else "blue")
        console.print(Panel(content, title=f"[{style}]{role.upper()}[/{style}]",
                            border_style=style, padding=(0, 1)))


def config_wizard():
    """Interactive configuration wizard."""
    console.print(Panel("⚙ Configuration Wizard", border_style="cyan", padding=(0, 1)))

    # Provider selection
    console.print("\n[bold]Select provider:[/bold]")
    providers = list(PROVIDERS.keys())
    for i, p in enumerate(providers):
        mark = "★" if p == config.provider else " "
        name = PROVIDERS[p]["name"]
        console.print(f"  [{i+1}] {mark} {name} ({p})")

    choice = _prompt_input("Provider [1-4] (Enter to keep current): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(providers):
        new_provider = providers[int(choice) - 1]
        config.set("provider", new_provider)
        console.print(f"[success]Provider set to: {new_provider}[/success]")

    # API key
    provider = config.provider
    pname = PROVIDERS.get(provider, {}).get("name", provider)
    existing_key = config.get_api_key(provider)
    display_key = f"{existing_key[:8]}…" if len(existing_key) > 8 else ("(not set)" if not existing_key else existing_key)
    console.print(f"\n[bold]{pname} API Key[/bold] (current: {display_key})")

    if provider == "openrouter":
        console.print("[dim]Get free key at: https://openrouter.ai/[/dim]")
    elif provider == "groq":
        console.print("[dim]Get free key at: https://console.groq.com/[/dim]")
    elif provider == "anthropic":
        console.print("[dim]Get key at: https://console.anthropic.com/[/dim]")
    elif provider == "openai":
        console.print("[dim]Get key at: https://platform.openai.com/[/dim]")
    elif provider == "ollama":
        console.print("[dim]No real key needed — install Ollama from ollama.com and run it locally.[/dim]")

    new_key = _prompt_input("API Key (Enter to keep): ").strip()
    if new_key:
        config.set_api_key(provider, new_key)
        console.print("[success]API key saved.[/success]")

    # Model selection — live, with pricing/context shown
    with console.status("[dim]Fetching available models...[/dim]", spinner="dots"):
        models, source = config.get_live_models(provider)
    if models:
        console.print(f"\n[bold]Available models for {pname}[/bold] [dim](source: {source})[/dim]:")
        for i, m in enumerate(models[:40]):
            mark = "★" if m.id == config.model else " "
            console.print(f"  [{i+1:2d}] {mark} {m.id}  [dim]({m.context_label()} ctx, {m.price_label()})[/dim]")
        if len(models) > 40:
            console.print(f"  [dim]... and {len(models) - 40} more — use /models <search> to find them[/dim]")

        choice = _prompt_input("Model number (Enter to keep current): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= min(40, len(models)):
            new_model = models[int(choice) - 1].id
            config.set("model", new_model)
            console.print(f"[success]Model set to: {new_model}[/success]")

    # Workspace
    console.print(f"\n[bold]Workspace[/bold] (current: {config.workspace})")
    new_ws = _prompt_input("Workspace path (Enter to keep): ").strip()
    if new_ws and os.path.isdir(new_ws):
        config.set("workspace", os.path.abspath(new_ws))
        console.print(f"[success]Workspace set to: {new_ws}[/success]")
    elif new_ws:
        console.print("[warning]Directory not found, keeping current.[/warning]")

    console.print(Panel("[success]Configuration saved![/success]", border_style="green"))


def _prompt_input(prompt: str) -> str:
    """Simple input with fallback for environments that don't support prompt_toolkit."""
    try:
        from prompt_toolkit import prompt as pt_prompt
        return pt_prompt(HTML(f"<ansiyellow>{prompt}</ansiyellow>"))
    except Exception:
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return ""


def show_docs():
    docs = """
# AIdex AI Coding Agent — Documentation

## Overview
AIdex is a professional CLI AI coding agent that connects to multiple AI providers
(OpenRouter, Groq, Anthropic, OpenAI) to help you write, edit, debug, and manage code.

## Getting Started
1. Run `aidex.py` (or `python aidex.py`)
2. Type `/config` to set your API key and choose a model
3. Start chatting! Ask AIdex to write code, fix bugs, create files, run commands, etc.

## Free Models (No credit card required)
- **OpenRouter**: mistralai/mistral-7b-instruct:free, meta-llama/llama-3.1-8b-instruct:free, and more
- **Groq**: llama-3.1-8b-instant, llama-3.1-70b-versatile, mixtral-8x7b-32768, and more

## Example Prompts
- "Create a Python Flask REST API with CRUD operations for a todo list"
- "Read main.py and fix any bugs you find"
- "Analyze this project and suggest improvements"
- "Create a Dockerfile for this Python application"
- "Refactor this code to use async/await"
- "Write unit tests for the functions in utils.py"
- "Run the tests and fix any failures"

## Tool System
AIdex automatically calls tools to perform real actions:
- File operations (read, write, edit, delete, move, copy)
- Shell commands (run any shell command)
- Git operations (status, diff, commit, log)
- Python execution (run code snippets)
- Search (find files, grep content)
- Project analysis

## Workspace
Set your workspace with `/workspace <path>` or in `/config`.
All file operations are relative to the workspace.

## Safe Mode
When safe mode is ON (default), dangerous commands like `rm -rf /` are blocked.
Toggle with `/safemode`.

## Session Management
- `/save [file]` — Save conversation to JSON
- `/load <file>` — Load a previous conversation
- `/clear` — Clear current conversation

## Configuration File
Config is stored at:
- Windows: %APPDATA%\\aidex\\config.json
- macOS: ~/Library/Application Support/aidex/config.json
- Linux: ~/.config/aidex/config.json

## API Providers
| Provider   | Free Models | Paid Models | Get Key |
|------------|-------------|-------------|---------|
| OpenRouter | Yes         | Yes         | openrouter.ai |
| Groq       | Yes (fast!) | No          | console.groq.com |
| Anthropic  | No          | Yes         | console.anthropic.com |
| OpenAI     | No          | Yes         | platform.openai.com |
"""
    console.print(Markdown(docs))


def show_credits():
    credits = """
# AIdex AI Coding Agent — Credits

**Version**: 1.0.0  
**License**: Apache 2.0

## Built With
- **Python** — Core language (3.6+ compatible, 32/64-bit)
- **Rich** — Beautiful terminal formatting (github.com/Textualize/rich)
- **prompt_toolkit** — Interactive terminal input (github.com/prompt-toolkit/python-prompt-toolkit)
- **urllib** — HTTP requests (Python stdlib, zero extra dependencies for core)

## AI Providers Supported
- **OpenRouter** (openrouter.ai) — Gateway to 100+ models, many FREE
- **Groq** (groq.com) — Ultra-fast LLM inference, FREE tier available
- **Anthropic** (anthropic.com) — Claude models
- **OpenAI** (openai.com) — GPT models

## Design Philosophy
AIdex was designed to be:
- **Dependency-light**: Core works with just Python stdlib
- **Cross-platform**: Windows 7+, Linux, macOS (32 and 64-bit)
- **Open**: Apache 2.0 — use it, modify it, build on it
- **Professional**: Real tool execution, not just code suggestions

## Special Thanks
To the open-source AI community and everyone building free/open models.
"""
    console.print(Markdown(credits))


def show_terms():
    terms = """
# Terms and Conditions

**AIdex AI Coding Agent** — Version 1.2.0  
**License**: Apache 2.0  
**Effective Date**: 2024

## 1. Acceptance
By using AIdex, you agree to these terms. If you disagree, do not use the software.

## 2. License (Apache 2.0)
AIdex is licensed under the Apache License 2.0. You are free to:
- Use commercially and non-commercially
- Modify and distribute
- Patent use (subject to Apache 2.0 terms)
- Private use

Subject to:
- Including the license notice
- Stating changes made to the code

## 3. API Usage
- You are responsible for your own API keys and usage
- API costs are determined by your chosen provider (OpenRouter, Groq, etc.)
- AIdex does NOT collect, store, or transmit your API keys beyond your local machine
- You must comply with each provider's Terms of Service

## 4. Tool Execution (File Operations & Shell Commands)
- AIdex can execute shell commands and modify files on your system
- **YOU ARE RESPONSIBLE** for reviewing commands before they execute
- Safe Mode (enabled by default) blocks some dangerous commands
- Disabling Safe Mode is at your own risk
- Always backup important files before using file-modifying features

## 5. Disclaimer of Warranties
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY.

## 6. Limitation of Liability
AIdex authors are not liable for:
- Data loss caused by file operations
- API costs incurred
- Security issues from running AI-suggested code
- Any other damages arising from use

## 7. AI-Generated Content
- AI responses may be incorrect, incomplete, or harmful
- Always review AI-generated code before executing in production
- The AI has access to your filesystem — use workspace restrictions appropriately

## 8. Prohibited Use
Do not use AIdex to:
- Create malware or harmful software
- Violate any laws or regulations
- Infringe on intellectual property rights
- Harm or harass others

## 9. Changes
These terms may be updated. Continued use constitutes acceptance.

## 10. Contact
Report issues at: https://github.com/Zelvior/AIdex
"""
    console.print(Markdown(terms))


def show_privacy():
    privacy = """
# Privacy Policy

**AIdex AI Coding Agent** — Version 1.2.0

## Summary
AIdex is a **local application**. It does NOT collect your data, track you, or phone home.

## What AIdex Does With Your Data

### API Keys
- Stored locally in your OS config directory only
- Never transmitted anywhere except to your chosen AI provider
- Never logged or sent to any AIdex server (there isn't one)

### Conversations
- Stored in memory during the session only
- Saved to disk only when you explicitly use `/save`
- Never transmitted to anyone except your chosen AI provider

### Files and Code
- File operations happen locally on your machine
- File contents sent to AI providers are only what you explicitly ask about
- AIdex does not scan, index, or upload your files without your request

### Usage Data
- **Zero telemetry** — AIdex collects absolutely no usage statistics
- No crash reports are sent automatically
- No analytics of any kind

## Third-Party AI Providers
When you send messages to AIdex:
1. Your message is sent to your configured AI provider (OpenRouter, Groq, etc.)
2. Each provider has their own privacy policy:
   - OpenRouter: https://openrouter.ai/privacy
   - Groq: https://groq.com/privacy-policy/
   - Anthropic: https://www.anthropic.com/privacy
   - OpenAI: https://openai.com/policies/privacy-policy

## Data Stored Locally
- `config.json` — Your settings and API keys (encrypted storage coming in future)
- `history.json` — Optional conversation history (if auto-save is enabled)
- These files are in your OS config directory and you can delete them at any time

## Children's Privacy
AIdex is not intended for children under 13.

## Changes to This Policy
Updates will be noted in the changelog.

## Contact
Concerns: https://github.com/Zelvior/AIdex/issues
"""
    console.print(Markdown(privacy))


def show_license():
    console.print(Panel("""
[bold cyan]Apache License, Version 2.0[/bold cyan]

Copyright 2024-2026 AIdex Contributors (originally Nexus AI Coding Agent)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at:

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

[dim]Full license text: https://www.apache.org/licenses/LICENSE-2.0[/dim]
""", title="License", border_style="cyan"))


# ─── MAIN APP ────────────────────────────────────────────────────────────────

class AIdexApp:
    def __init__(self):
        self._setup_callbacks()
        self._session = self._create_session()

    def _setup_callbacks(self):
        agent.set_callbacks(
            on_tool_call=lambda name, params: print_tool_call(name, params),
            on_tool_result=lambda name, result: print_tool_result(name, result),
        )

    def _create_session(self) -> PromptSession:
        history_file = str(config._data.get("history_file",
                           str(Path(str(config.get("workspace", "."))) / ".aidex_history")))
        try:
            hist = FileHistory(os.path.join(str(Path.home()), ".aidex_prompt_history"))
        except Exception:
            hist = None

        pt_style = PTStyle.from_dict({
            "": "#ffffff",
            "prompt": "#00ff88 bold",
        })

        return PromptSession(
            history=hist,
            auto_suggest=AutoSuggestFromHistory(),
            completer=COMMAND_COMPLETER,
            style=pt_style,
            complete_while_typing=True,
        )

    def _get_user_input(self) -> str:
        try:
            provider_short = config.provider[:3].upper()
            model_short = config.model.split("/")[-1][:15]
            prompt_text = HTML(
                f'<ansigreen><b>you</b></ansigreen>'
                f'<ansiblue>[{provider_short}:{model_short}]</ansiblue>'
                f'<ansiyellow> ❯ </ansiyellow>'
            )
            return self._session.prompt(prompt_text)
        except KeyboardInterrupt:
            return ""
        except EOFError:
            return "/exit"

    def _handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if handled."""
        parts = cmd.strip().split(None, 1)
        if not parts:
            return False
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command in ("/exit", "/quit"):
            console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]\n")
            sys.exit(0)

        elif command == "/help":
            show_help()

        elif command == "/config":
            config_wizard()

        elif command == "/models":
            mq, msort, mfree, mrefresh = _parse_models_args(arg)
            show_models(query=mq, sort_by=msort, free_only=mfree, refresh=mrefresh)

        elif command == "/model":
            if arg:
                _switch_model(arg.strip())
            else:
                show_models()

        elif command == "/provider":
            if arg and arg.strip() in PROVIDERS:
                new_provider = arg.strip()
                config.set("provider", new_provider)
                # Pick a sensible default model for the new provider: prefer
                # a live free model, fall back to the static list, never crash.
                try:
                    with console.status("[dim]Finding a default model...[/dim]", spinner="dots"):
                        models, _src = config.get_live_models(new_provider)
                    free = [m for m in models if m.is_free]
                    pick = (free[0] if free else models[0]) if models else None
                    if pick:
                        config.set("model", pick.id)
                except Exception:
                    static = config.all_models(new_provider)
                    if static:
                        config.set("model", static[0])
                console.print(f"[success]Provider set to: {new_provider}, model: {config.model}[/success]")
            else:
                console.print(f"[warning]Available providers: {', '.join(PROVIDERS.keys())}[/warning]")

        elif command == "/workspace":
            if arg:
                ws = os.path.abspath(arg.strip())
                if os.path.isdir(ws):
                    config.set("workspace", ws)
                    console.print(f"[success]Workspace: {ws}[/success]")
                else:
                    console.print(f"[error]Not a directory: {ws}[/error]")
            else:
                console.print(f"Current workspace: {config.workspace}")

        elif command == "/clear":
            agent.clear_history()
            console.clear()
            show_banner()
            console.print("[success]Conversation cleared.[/success]")

        elif command == "/history":
            show_history()

        elif command == "/save":
            fname = arg.strip() or f"aidex_session_{int(time.time())}.json"
            try:
                agent.save_session(fname)
                console.print(f"[success]Saved to: {fname}[/success]")
            except Exception as e:
                console.print(f"[error]Save failed: {e}[/error]")

        elif command == "/load":
            if not arg:
                console.print("[warning]Usage: /load <file>[/warning]")
            else:
                try:
                    agent.load_session(arg.strip())
                    console.print(f"[success]Loaded: {arg.strip()} ({len(agent.messages)} messages)[/success]")
                except Exception as e:
                    console.print(f"[error]Load failed: {e}[/error]")

        elif command == "/status":
            show_status()

        elif command == "/tools":
            show_tools()

        elif command == "/run":
            if arg:
                from src.tools.file_tools import run_command
                result = run_command(arg.strip(), config.workspace, safe_mode=config.get("safe_mode", True))
                print_tool_result("run_command", result)
            else:
                console.print("[warning]Usage: /run <command>[/warning]")

        elif command == "/read":
            if arg:
                from src.tools.file_tools import read_file
                result = read_file(arg.strip(), config.workspace)
                print_tool_result("read_file", result)
            else:
                console.print("[warning]Usage: /read <file>[/warning]")

        elif command == "/ls":
            from src.tools.file_tools import list_directory
            result = list_directory(arg.strip() or ".", config.workspace)
            print_tool_result("list_directory", result)

        elif command == "/analyze":
            from src.tools.file_tools import analyze_project
            result = analyze_project(config.workspace)
            print_tool_result("analyze_project", result)

        elif command == "/disk":
            from src.tools.file_tools import disk_usage
            result = disk_usage(arg.strip() or ".", config.workspace)
            print_tool_result("disk_usage", result)

        elif command == "/env":
            from src.tools.file_tools import env_info
            result = env_info()
            print_tool_result("env_info", result)

        elif command == "/which":
            if arg:
                from src.tools.file_tools import which
                result = which(arg.strip())
                print_tool_result("which", result)
            else:
                console.print("[warning]Usage: /which <name>[/warning]")

        elif command == "/safemode":
            new_val = not config.get("safe_mode", True)
            config.set("safe_mode", new_val)
            state = "ON 🔒" if new_val else "OFF ⚠️"
            console.print(f"[bold]Safe mode: {state}[/bold]")

        elif command == "/docs":
            show_docs()

        elif command == "/credits":
            show_credits()

        elif command == "/terms":
            show_terms()

        elif command == "/privacy":
            show_privacy()

        elif command == "/license":
            show_license()

        else:
            return False  # Not a known command

        return True

    def _stream_response(self, user_input: str):
        """Stream AI response to the terminal."""
        console.print()
        console.print(Rule("[bold blue]AIdex[/bold blue]", style="dim blue"))

        full_text = []
        tool_calls_made = []
        has_error = False

        # We'll collect text and render it live
        current_text = []

        for typ, content in agent.chat_stream(user_input):
            if typ == "text":
                current_text.append(content)
                # Print text as it streams
                console.print(content, end="", highlight=False)

            elif typ == "tool_call":
                # Flush current text
                console.print()  # newline after streamed text
                current_text = []

            elif typ == "tool_result":
                pass  # Already printed via callbacks

            elif typ == "error":
                console.print()
                console.print(Panel(
                    Text(content, style="bold red"),
                    title="[red]Error[/red]",
                    border_style="red",
                ))
                has_error = True

            elif typ == "done":
                console.print()  # Final newline

        if not has_error:
            # Re-render the collected text as markdown (for clean formatting)
            pass  # Already streamed above

        console.print(Rule(style="dim blue"))
        console.print()

    def run(self):
        """Main application loop."""
        # Check for first-run setup
        if not config.get_api_key():
            show_banner()
            console.print(Panel(
                "[bold yellow]Welcome to AIdex! 🎉[/bold yellow]\n\n"
                "To get started, you need to configure your AI provider API key.\n\n"
                "[bold]Free options:[/bold]\n"
                "• [cyan]OpenRouter[/cyan]: openrouter.ai (many free models)\n"
                "• [cyan]Groq[/cyan]: console.groq.com (fast, free)\n\n"
                "[bold]Offline / low-end option:[/bold]\n"
                "• [cyan]Ollama[/cyan]: ollama.com — runs fully local, no API key, no internet\n\n"
                "Run [bold magenta]/config[/bold magenta] to set up your API key.",
                title="First Run Setup",
                border_style="cyan",
            ))
        else:
            show_banner()

        status_bar()
        console.print(
            "[dim]Type a message to chat, or use [bold]/help[/bold] for commands. "
            "[bold]/exit[/bold] to quit.[/dim]\n"
        )

        while True:
            try:
                user_input = self._get_user_input()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]\n")
                break

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.strip().startswith("/"):
                handled = self._handle_command(user_input.strip())
                if not handled:
                    console.print(f"[warning]Unknown command. Type /help for list.[/warning]")
                continue

            # Send to AI
            self._stream_response(user_input)
