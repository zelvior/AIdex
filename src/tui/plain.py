# -*- coding: utf-8 -*-
"""
AIdex Plain TUI - Zero-dependency fallback interface.
Apache 2.0 License

Used automatically when Rich and/or prompt_toolkit are unavailable or fail to
import/run (old Python, Windows XP, 32-bit systems, minimal environments).
Uses only the standard library: print(), input(), os, sys.
Compatible with Python 2.7 and Python 3.x.

This module intentionally avoids: f-strings (Python 2 compat), type hints,
pathlib (optional), and any third-party import.
"""

import os
import sys
import time
import platform

try:
    string_types = (str, unicode)  # Python 2  # noqa: F821
except NameError:
    string_types = (str,)

VERSION = "1.3.0"

BANNER = r"""
   ___    ____    __
  / _ |  /  _/___/ /__ __
 / __ | _/ // _  / -_) \ /
/_/ |_|/___/\_,_/\__/_\_\

  AIdex - AI Coding Agent (Plain Mode) v%s
""" % VERSION


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if platform.system() == "Windows":
        # Old cmd.exe (XP/7) generally lacks ANSI support without extra setup.
        return os.environ.get("ANSICON") is not None or "WT_SESSION" in os.environ
    return sys.stdout.isatty()


_COLOR = _supports_color()


def _c(text, code):
    if not _COLOR:
        return text
    return "\033[%sm%s\033[0m" % (code, text)


def green(t):
    return _c(t, "32")


def yellow(t):
    return _c(t, "33")


def red(t):
    return _c(t, "31")


def cyan(t):
    return _c(t, "36")


def dim(t):
    return _c(t, "2")


def safe_input(prompt):
    """input() that degrades gracefully under odd encodings / old consoles."""
    try:
        if sys.version_info[0] < 3:
            return raw_input(prompt).decode(sys.stdin.encoding or "utf-8", "replace")  # noqa: F821
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return "/exit"
    except Exception:
        try:
            sys.stdout.write(prompt)
            sys.stdout.flush()
            line = sys.stdin.readline()
            return line.rstrip("\n")
        except Exception:
            return "/exit"


def out(text=""):
    try:
        print(text)
    except UnicodeEncodeError:
        # Very old consoles (cmd.exe on XP with default codepage) may choke
        # on non-ASCII. Strip to ASCII as a last resort.
        if sys.version_info[0] < 3 and isinstance(text, unicode):  # noqa: F821
            print(text.encode("ascii", "replace"))
        else:
            print(text.encode("ascii", "replace").decode("ascii"))


COMMANDS = [
    ("/help", "Show this help"),
    ("/config", "Configure API key, provider, model, workspace"),
    ("/models", "List live models (try: /models free, /models sort price, /models refresh)"),
    ("/model <name>", "Switch model (fuzzy-matched against live list)"),
    ("/provider <name>", "Switch provider (openrouter/groq/anthropic/openai/ollama)"),
    ("/workspace <path>", "Change workspace directory"),
    ("/clear", "Clear conversation history"),
    ("/history", "Show conversation history"),
    ("/save [file]", "Save conversation to file"),
    ("/load <file>", "Load conversation from file"),
    ("/status", "Show current status"),
    ("/tools", "List available tools"),
    ("/run <cmd>", "Run a shell command directly"),
    ("/read <file>", "Read a file directly"),
    ("/ls [path]", "List directory contents"),
    ("/analyze", "Analyze project structure"),
    ("/disk [path]", "Show disk usage and directory size"),
    ("/env", "Show Python/OS/architecture info"),
    ("/which <name>", "Locate an executable on PATH"),
    ("/image <prompt>", "Generate an image (free by default, no API key needed)"),
    ("/ralph", "Show the Ralph task loop status"),
    ("/ralph add <title>", "Add a task to the Ralph loop"),
    ("/ralph run [n]", "Run the Ralph loop autonomously (default cap: 35 iterations)"),
    ("/ralph clear", "Clear all Ralph tasks"),
    ("/safemode", "Toggle safe mode"),
    ("/docs", "Show documentation"),
    ("/credits", "Show credits"),
    ("/terms", "Show terms and conditions"),
    ("/privacy", "Show privacy policy"),
    ("/license", "Show Apache 2.0 license info"),
    ("/exit", "Exit AIdex"),
    ("/quit", "Exit AIdex"),
]


def show_banner():
    out(cyan(BANNER))
    out(dim("Type a message to chat, or /help for commands. /exit to quit."))
    out("")


def show_help():
    out(cyan("AIdex Commands"))
    out(cyan("--------------"))
    for cmd, desc in COMMANDS:
        out("  %-22s %s" % (cmd, desc))
    out("")


def status_line(config):
    provider = config.provider
    model = config.model
    ws = config.workspace
    safe = "ON" if config.get("safe_mode") else "OFF"
    key_ok = "set" if config.has_usable_key() else "MISSING"
    out(dim("-" * 60))
    out("Provider: %s   Model: %s" % (provider, model))
    out("Workspace: %s" % ws)
    out("Key: %s   SafeMode: %s" % (key_ok, safe))
    out(dim("-" * 60))


def show_status(config, agent):
    out(cyan("AIdex Status"))
    out("  Version:      %s" % VERSION)
    out("  Python:       %s" % sys.version.split()[0])
    bits = "64-bit" if sys.maxsize > 2 ** 32 else "32-bit"
    out("  Architecture: %s (%s)" % (platform.machine(), bits))
    out("  Platform:     %s %s" % (platform.system(), platform.release()))
    out("  Provider:     %s" % config.provider)
    out("  Model:        %s" % config.model)
    out("  API Key:      %s" % ("set" if config.has_usable_key() else "NOT set"))
    out("  Workspace:    %s" % config.workspace)
    out("  Safe Mode:    %s" % ("ON" if config.get("safe_mode") else "OFF"))
    out("  Messages:     %d" % len(agent.messages))
    out("")


def _parse_models_args(arg):
    """Parse '/models <free|refresh|sort X|search terms>' into
    (query, sort_by, free_only, refresh). Mirrors app.py's parser."""
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


def show_models(config, query="", sort_by="name", free_only=False, refresh=False):
    from src.core.models import filter_models, sort_models

    provider = config.provider
    info = config.get_provider_info()
    pname = info.get("name", provider)

    out(dim("Fetching live models for %s..." % pname))
    models, source = config.get_live_models(force_refresh=refresh)
    shown = sort_models(filter_models(models, query, free_only), sort_by)

    source_label = {
        "live": "live",
        "cache": "cached",
        "stale-cache": "cached (stale, refetch failed)",
        "static-fallback": "built-in fallback (no network/cache)",
    }.get(source, source)
    age = config.models_cache_age() if source != "live" else "just now"

    title = "Models - %s" % pname
    if query:
        title += "  (filter: '%s')" % query
    out(cyan(title))
    for m in shown[:80]:
        mark = "*" if m.id == config.model else " "
        tools_mark = " tools=yes" if m.supports_tools else ("" if m.supports_tools is None else " tools=no")
        out(" %s %-42s ctx=%-6s %-18s%s" % (mark, m.id, m.context_label(), m.price_label(), tools_mark))
    out(dim("* = current model   |   %d of %d shown   |   source: %s (%s)" %
            (len(shown), len(models), source_label, age)))
    out(dim("Tip: /models <search>, /models free, /models sort price|context|name, /models refresh"))
    out("")


def switch_model(config, arg):
    """Switch model with fuzzy matching against the live model list."""
    from src.core.models import filter_models
    out(dim("Checking model..."))
    models, source = config.get_live_models()
    exact = [m for m in models if m.id == arg]
    if exact:
        config.set("model", arg)
        out(green("Model set to: %s" % arg))
        return
    matches = filter_models(models, arg)
    if len(matches) == 1:
        config.set("model", matches[0].id)
        out(green("Model set to: %s (matched '%s')" % (matches[0].id, arg)))
    elif len(matches) > 1:
        out(yellow("'%s' matches %d models - be more specific:" % (arg, len(matches))))
        for m in matches[:15]:
            out("  %s" % m.id)
    else:
        config.set("model", arg)
        out(yellow("'%s' not found in known models for this provider - set anyway." % arg))


def _status_icon(status):
    return {"pending": " ", "in_progress": ">", "done": "x",
            "failed": "!", "skipped": "-"}.get(status, "?")


def show_ralph_status(state):
    out(cyan("Ralph Task Loop"))
    if not state.tasks:
        out(dim("No tasks yet. Add one with: /ralph add <title>"))
        out("")
        return
    counts = state.counts()
    out(dim("Tasks file: %s" % state.tasks_path))
    out(dim("pending=%d  in_progress=%d  done=%d  failed=%d  skipped=%d  (iteration %d)" % (
        counts["pending"], counts["in_progress"], counts["done"],
        counts["failed"], counts["skipped"], state.iteration)))
    out("")
    for t in state.tasks:
        icon = _status_icon(t.status)
        color = {"done": green, "failed": red, "in_progress": yellow}.get(t.status, dim)
        out(color("  [%s] #%s %s" % (icon, t.id, t.title)))
        if t.notes:
            out(dim("        %s" % t.notes[:100]))
    out("")
    out(dim("/ralph run [max_iterations] to work through pending tasks autonomously"))
    out("")


def run_ralph_loop(config, agent, state, max_iterations):
    from src.core.ralph import RalphRunner

    pending_count = sum(1 for t in state.tasks if t.status == "pending")
    if pending_count == 0:
        out(yellow("No pending tasks. Add one with: /ralph add <title>"))
        return

    out(cyan("Starting Ralph loop: %d pending task(s), cap %d iteration(s)" % (pending_count, max_iterations)))
    out(dim("Each task runs as its own focused agent turn. Ctrl+C to stop after the current task."))
    out("")

    runner = RalphRunner(agent, state, max_iterations=max_iterations)

    def on_start(task, index, total):
        out(cyan("--- Task %d/%d: %s ---" % (index, total, task.title)))

    def on_event(task, etype, content):
        if etype == "text":
            sys.stdout.write(content)
            sys.stdout.flush()
        elif etype == "tool_call":
            out("")
            out(yellow("  > %s(...)" % content))
        elif etype == "tool_result":
            pass
        elif etype == "error":
            out("")
            out(red("  Error: %s" % content))

    def on_done(task, outcome):
        out("")
        if outcome == "done":
            out(green("--- Task #%s complete ---" % task.id))
        else:
            out(red("--- Task #%s failed ---" % task.id))
        out("")

    def on_finished(reason):
        labels = {
            "completed": "All tasks complete!",
            "max_iterations": "Stopped: hit the iteration cap (%d). Run /ralph run again to continue." % max_iterations,
            "stopped": "Stopped by request. Run /ralph run again to resume.",
            "no_tasks": "No tasks to run.",
        }
        out(cyan(labels.get(reason, "Finished: %s" % reason)))

    try:
        runner.run(on_task_start=on_start, on_task_event=on_event,
                   on_task_done=on_done, on_finished=on_finished)
    except KeyboardInterrupt:
        runner.request_stop()
        out("")
        out(yellow("Stopping after current task..."))


def show_tools():
    from src.tools.file_tools import TOOL_DEFINITIONS
    out(cyan("Available Tools"))
    for t in TOOL_DEFINITIONS:
        params = ", ".join(t["parameters"].keys())
        out("  %-22s %s" % (t["name"], t["description"]))
        if params:
            out("    params: %s" % params)
    out("")


def show_history(agent):
    from src.core.agent import normalize_message_content
    msgs = agent.get_history()
    if not msgs:
        out(dim("No conversation history."))
        return
    for msg in msgs:
        role = msg.get("role", "?")
        content = normalize_message_content(msg)
        if len(content) > 300:
            content = content[:300] + "..."
        out("[%s] %s" % (role.upper(), content))
    out("")


def print_tool_call(name, params):
    params_str = ", ".join("%s=%s" % (k, repr(v)[:40]) for k, v in params.items())
    out(yellow("  > %s(%s)" % (name, params_str)))


def print_tool_result(name, result):
    icon = "OK" if result.success else "FAIL"
    color = green if result.success else red
    output = str(result.output or result.error)
    if len(output) > 2000:
        output = output[:2000] + "\n... [truncated]"
    out(color("  [%s] %s" % (icon, name)))
    for line in output.splitlines():
        out("    " + line)


def config_wizard(config, PROVIDERS, IMAGE_PROVIDERS=None):
    out(cyan("Configuration Wizard"))
    providers = list(PROVIDERS.keys())
    for i, p in enumerate(providers):
        mark = "*" if p == config.provider else " "
        out("  [%d] %s %s (%s)" % (i + 1, mark, PROVIDERS[p]["name"], p))
    choice = safe_input("Provider [1-%d] (Enter to keep current): " % len(providers)).strip()
    if choice.isdigit() and 1 <= int(choice) <= len(providers):
        new_provider = providers[int(choice) - 1]
        config.set("provider", new_provider)
        out(green("Provider set to: %s" % new_provider))

    provider = config.provider
    pname = PROVIDERS.get(provider, {}).get("name", provider)
    existing_key = config.get_api_key(provider)
    display_key = (existing_key[:8] + "...") if len(existing_key) > 8 else (existing_key or "(not set)")
    out("")
    out("%s API Key (current: %s)" % (pname, display_key))
    if provider == "ollama":
        out(dim("Ollama runs locally - no real key needed. Base URL set separately."))
    elif provider == "pollinations":
        out(dim("No key needed - free, no signup. A key only raises your rate limit."))
    elif provider == "gemini":
        out(dim("Get a free key at: https://aistudio.google.com/apikey"))
    elif provider == "custom":
        out(dim("Point this at any OpenAI-compatible /chat/completions API."))
        current_url = config.get("custom_base_url", "")
        new_url = safe_input("Base URL (current: %s): " % (current_url or "(not set)")).strip()
        if new_url:
            config.set("custom_base_url", new_url)
            out(green("Base URL set to: %s" % new_url))
    new_key = safe_input("API Key (Enter to keep): ").strip()
    if new_key:
        config.set_api_key(provider, new_key)
        out(green("API key saved."))

    out(dim("Fetching available models..."))
    models, source = config.get_live_models(provider)
    if models:
        out("")
        out("Available models for %s (source: %s):" % (pname, source))
        for i, m in enumerate(models[:40]):
            mark = "*" if m.id == config.model else " "
            out("  [%2d] %s %s  (%s ctx, %s)" % (i + 1, mark, m.id, m.context_label(), m.price_label()))
        if len(models) > 40:
            out("  ... and %d more - use /models <search> to find them" % (len(models) - 40))
        choice = safe_input("Model number (Enter to keep current): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= min(40, len(models)):
            new_model = models[int(choice) - 1].id
            config.set("model", new_model)
            out(green("Model set to: %s" % new_model))

    if IMAGE_PROVIDERS:
        cur_img_provider = config.get("image_provider", "pollinations")
        out("")
        out("Image generation (current: %s)" % IMAGE_PROVIDERS.get(cur_img_provider, {}).get("name", "?"))
        img_providers = list(IMAGE_PROVIDERS.keys())
        for i, p in enumerate(img_providers):
            mark = "*" if p == cur_img_provider else " "
            out("  [%d] %s %s (%s)" % (i + 1, mark, IMAGE_PROVIDERS[p]["name"], p))
        choice = safe_input("Image provider [1-%d] (Enter to keep current): " % len(img_providers)).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(img_providers):
            new_img_provider = img_providers[int(choice) - 1]
            config.set("image_provider", new_img_provider)
            out(green("Image provider set to: %s" % new_img_provider))
            if new_img_provider == "custom":
                current_url = config.get("image_base_url", "")
                new_url = safe_input("Image API base URL (current: %s): " % (current_url or "(not set)")).strip()
                if new_url:
                    config.set("image_base_url", new_url)
                new_img_key = safe_input("Image API key (Enter to skip): ").strip()
                if new_img_key:
                    config.set("image_api_key", new_img_key)
        elif cur_img_provider == "pollinations":
            out(dim("Free, no signup, no key needed."))

    out("")
    out("Workspace (current: %s)" % config.workspace)
    new_ws = safe_input("Workspace path (Enter to keep): ").strip()
    if new_ws and os.path.isdir(new_ws):
        config.set("workspace", os.path.abspath(new_ws))
        out(green("Workspace set to: %s" % new_ws))
    elif new_ws:
        out(yellow("Directory not found, keeping current."))

    out(green("Configuration saved."))
    out("")


def show_docs():
    out(cyan("AIdex Documentation"))
    out("""
Overview
  AIdex connects to multiple AI providers (OpenRouter, Groq, Anthropic,
  OpenAI, Ollama-local) to help write, edit, debug, and manage code.

Getting Started
  1. Run aidex.py
  2. Type /config to set provider/key/model
  3. Chat normally, or use slash commands.

Low-End / Offline Mode
  Set provider to 'ollama' to use a fully local, free model with no
  internet connection required (requires Ollama installed separately).

Free Models
  OpenRouter and Groq both offer free-tier models requiring no card.
""")


def show_credits():
    out(cyan("AIdex - Credits"))
    out("""
Version: %s
License: Apache 2.0

Built with: Python standard library only (plain mode), optionally
Rich + prompt_toolkit for the enhanced interface.

Providers: OpenRouter, Groq, Anthropic, OpenAI, Ollama (local).
Originally based on the Nexus AI Coding Agent project.
""" % VERSION)


def show_terms():
    out("""Terms and Conditions - AIdex AI Coding Agent
License: Apache 2.0

By using AIdex you agree to use it at your own risk. AIdex can execute
shell commands and modify files on your system. Review commands and
back up important files before disabling Safe Mode. The software is
provided "AS IS" without warranty of any kind.
""")


def show_privacy():
    out("""Privacy Policy - AIdex
AIdex is a local application. It does not collect telemetry, track
usage, or phone home. API keys are stored locally in your OS config
directory and sent only to your chosen AI provider. Conversations are
kept in memory and saved to disk only when you explicitly use /save.
""")


def show_license():
    out("""Apache License, Version 2.0

Licensed under the Apache License, Version 2.0. You may obtain a copy
at: http://www.apache.org/licenses/LICENSE-2.0

Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
ANY KIND, either express or implied.
""")


class PlainApp(object):
    """Minimal, dependency-free terminal app. Mirrors the Rich-based
    NexusApp/AIdexApp feature set so functionality is identical, just
    without fancy rendering."""

    def __init__(self):
        from src.core.config import config, PROVIDERS, IMAGE_PROVIDERS
        from src.core.agent import agent
        from src.core.ralph import RalphState, default_tasks_path
        self.config = config
        self.PROVIDERS = PROVIDERS
        self.IMAGE_PROVIDERS = IMAGE_PROVIDERS
        self.agent = agent
        self.ralph_state = RalphState(default_tasks_path(config.workspace))
        self.ralph_state.load()
        self.agent.set_callbacks(
            on_tool_call=lambda name, params: print_tool_call(name, params),
            on_tool_result=lambda name, result: print_tool_result(name, result),
        )

    def _handle_command(self, cmd):
        parts = cmd.strip().split(None, 1)
        if not parts:
            return False
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        config = self.config
        agent = self.agent
        PROVIDERS = self.PROVIDERS
        IMAGE_PROVIDERS = self.IMAGE_PROVIDERS

        if command in ("/exit", "/quit"):
            out(cyan("Goodbye!"))
            sys.exit(0)
        elif command == "/help":
            show_help()
        elif command == "/config":
            config_wizard(config, PROVIDERS, IMAGE_PROVIDERS)
        elif command == "/models":
            mq, msort, mfree, mrefresh = _parse_models_args(arg)
            show_models(config, query=mq, sort_by=msort, free_only=mfree, refresh=mrefresh)
        elif command == "/model":
            if arg:
                switch_model(config, arg.strip())
            else:
                show_models(config)
        elif command == "/provider":
            if arg and arg.strip() in PROVIDERS:
                new_provider = arg.strip()
                config.set("provider", new_provider)
                try:
                    out(dim("Finding a default model..."))
                    models, _src = config.get_live_models(new_provider)
                    free = [m for m in models if m.is_free]
                    pick = (free[0] if free else models[0]) if models else None
                    if pick:
                        config.set("model", pick.id)
                except Exception:
                    static = config.all_models(new_provider)
                    if static:
                        config.set("model", static[0])
                out(green("Provider set to: %s, model: %s" % (new_provider, config.model)))
            else:
                out(yellow("Available providers: %s" % ", ".join(PROVIDERS.keys())))
        elif command == "/workspace":
            if arg:
                ws = os.path.abspath(arg.strip())
                if os.path.isdir(ws):
                    config.set("workspace", ws)
                    out(green("Workspace: %s" % ws))
                else:
                    out(red("Not a directory: %s" % ws))
            else:
                out("Current workspace: %s" % config.workspace)
        elif command == "/clear":
            agent.clear_history()
            out(green("Conversation cleared."))
        elif command == "/history":
            show_history(agent)
        elif command == "/save":
            fname = arg.strip() or ("aidex_session_%d.json" % int(time.time()))
            try:
                agent.save_session(fname)
                out(green("Saved to: %s" % fname))
            except Exception as e:
                out(red("Save failed: %s" % e))
        elif command == "/load":
            if not arg:
                out(yellow("Usage: /load <file>"))
            else:
                try:
                    agent.load_session(arg.strip())
                    out(green("Loaded: %s (%d messages)" % (arg.strip(), len(agent.messages))))
                except Exception as e:
                    out(red("Load failed: %s" % e))
        elif command == "/status":
            show_status(config, agent)
        elif command == "/tools":
            show_tools()
        elif command == "/run":
            if arg:
                from src.tools.file_tools import run_command
                result = run_command(arg.strip(), config.workspace, safe_mode=config.get("safe_mode", True))
                print_tool_result("run_command", result)
            else:
                out(yellow("Usage: /run <command>"))
        elif command == "/read":
            if arg:
                from src.tools.file_tools import read_file
                result = read_file(arg.strip(), config.workspace)
                print_tool_result("read_file", result)
            else:
                out(yellow("Usage: /read <file>"))
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
                out(yellow("Usage: /which <name>"))
        elif command == "/image":
            if arg:
                from src.tools.file_tools import generate_image
                out(dim("Generating image..."))
                result = generate_image(arg.strip(), config.workspace)
                print_tool_result("generate_image", result)
            else:
                out(yellow("Usage: /image <description of the image>"))
        elif command == "/ralph":
            sub_parts = arg.strip().split(None, 1)
            sub = sub_parts[0].lower() if sub_parts else ""
            sub_arg = sub_parts[1] if len(sub_parts) > 1 else ""

            if not sub:
                show_ralph_status(self.ralph_state)
            elif sub == "add":
                if not sub_arg:
                    out(yellow("Usage: /ralph add <task title>"))
                else:
                    task = self.ralph_state.add_task(sub_arg)
                    self.ralph_state.save()
                    out(green("Added task #%s: %s" % (task.id, task.title)))
            elif sub == "run":
                from src.core.ralph import DEFAULT_MAX_ITERATIONS
                cap = DEFAULT_MAX_ITERATIONS
                if sub_arg.strip().isdigit():
                    cap = int(sub_arg.strip())
                run_ralph_loop(config, agent, self.ralph_state, cap)
            elif sub == "clear":
                confirm = safe_input("Clear all %d Ralph task(s)? [y/N]: " % len(self.ralph_state.tasks)).strip().lower()
                if confirm == "y":
                    self.ralph_state.tasks = []
                    self.ralph_state.iteration = 0
                    self.ralph_state.save()
                    out(green("Ralph tasks cleared."))
                else:
                    out(dim("Cancelled."))
            else:
                out(yellow("Usage: /ralph [add <title> | run [max_iterations] | clear]"))
        elif command == "/safemode":
            new_val = not config.get("safe_mode", True)
            config.set("safe_mode", new_val)
            out("Safe mode: %s" % ("ON" if new_val else "OFF"))
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
            return False
        return True

    def _stream_response(self, user_input):
        out("")
        out(dim("AIdex:"))
        has_error = False
        for typ, content in self.agent.chat_stream(user_input):
            if typ == "text":
                sys.stdout.write(content)
                sys.stdout.flush()
            elif typ == "tool_call":
                out("")
            elif typ == "tool_result":
                pass
            elif typ == "error":
                out("")
                out(red("Error: %s" % content))
                has_error = True
            elif typ == "done":
                out("")
        out(dim("-" * 60))
        out("")

    def run(self):
        config = self.config
        if not config.has_usable_key():
            show_banner()
            out(yellow("Welcome to AIdex!"))
            out("To get started, configure an AI provider with /config")
            out("Free, zero-config (default): Pollinations - chat + images, no key needed")
            out("Other free options: OpenRouter (openrouter.ai), Groq (console.groq.com), Gemini (aistudio.google.com)")
            out("Offline option: Ollama (ollama.com) - no API key, no internet needed")
            out("Try it now: /image a sunset over mountains")
            out("")
        else:
            show_banner()

        status_line(config)
        out("")

        while True:
            try:
                provider_short = config.provider[:3].upper()
                model_short = config.model.split("/")[-1][:15]
                prompt_text = "you [%s:%s] > " % (provider_short, model_short)
                user_input = safe_input(prompt_text)
            except (KeyboardInterrupt, EOFError):
                out("")
                out(cyan("Goodbye!"))
                break

            if not user_input.strip():
                continue

            if user_input.strip().startswith("/"):
                handled = self._handle_command(user_input.strip())
                if not handled:
                    out(yellow("Unknown command. Type /help for list."))
                continue

            self._stream_response(user_input)


def main():
    app = PlainApp()
    app.run()


if __name__ == "__main__":
    main()
