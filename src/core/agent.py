#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex Agent Core - Orchestrates AI model + tool execution
Apache 2.0 License
"""

from __future__ import annotations
import re
import json
import time
from typing import Iterator, List, Dict, Any, Optional, Callable, Tuple

from src.core.config import config
from src.providers.base import create_provider, ProviderError
from src.tools.file_tools import (
    read_file, write_file, edit_file, patch_lines, append_file,
    delete_file, move_file, copy_file, create_directory, list_directory,
    search_files, grep_file, run_command, run_python,
    git_status, git_diff, git_log, git_add, git_commit, git_init, git_branch, git_checkout,
    analyze_project, get_file_info, read_file_lines, head_file, tail_file,
    count_lines, disk_usage, env_info, find_replace_in_files, which,
    TOOL_DEFINITIONS, ToolResult
)


SYSTEM_PROMPT = """You are AIdex, a professional AI coding agent. You help users with:
- Writing, editing, refactoring, and debugging code
- Managing files and directories
- Running commands and scripts
- Analyzing project structure
- Git operations
- Explaining code and concepts

## Tool Usage
Tools are available to you as native function calls — use them directly rather than describing them in text. If native function calling is unavailable for the current model, fall back to emitting this exact text format instead:

<tool_call>
{
  "tool": "tool_name",
  "params": {
    "param1": "value1",
    "param2": "value2"
  }
}
</tool_call>

You can call MULTIPLE tools in a single response. Always call tools when the task requires it.

## Available Tools
{tools}

## Rules
- Always use tools to actually perform tasks (don't just describe what you would do)
- For file creation/editing, use write_file or edit_file — never just show code without creating the file
- After using tools, explain what you did
- If safe_mode is on, dangerous commands are blocked automatically
- Be proactive: analyze the project first, then act
- For complex tasks, break them into steps and use multiple tool calls
- Always show diffs or summaries of changes made

## Workspace
Current workspace: {workspace}
"""

TOOL_SUMMARY = "\n".join(
    f"- **{t['name']}**: {t['description']}" for t in TOOL_DEFINITIONS
)


def normalize_message_content(msg: Dict) -> str:
    """Render any message's content as a display string, regardless of
    whether it's a plain string (legacy/text), None with tool_calls
    (OpenAI native tool request), a list of content blocks (Anthropic
    native tool request/result), or a 'tool' role result message."""
    content = msg.get("content")
    role = msg.get("role", "")

    if content is None and msg.get("tool_calls"):
        names = ", ".join(tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"])
        return f"[calling tool(s): {names}]"

    if isinstance(content, list):
        parts = []
        for block in content:
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(f"[calling tool: {block.get('name', '?')}]")
            elif btype == "tool_result":
                out = block.get("content", "")
                parts.append(f"[tool result]\n{out}")
            else:
                parts.append(str(block))
        return "\n".join(parts)

    if role == "tool":
        return f"[tool result: {msg.get('name', '?')}]\n{content or ''}"

    return content or ""


class Agent:
    def __init__(self):
        self.messages: List[Dict] = []
        self.total_tokens = 0
        self.session_start = time.time()
        self._provider = None
        self._on_tool_call: Optional[Callable] = None
        self._on_tool_result: Optional[Callable] = None

    def set_callbacks(self,
                      on_tool_call: Optional[Callable] = None,
                      on_tool_result: Optional[Callable] = None):
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result

    def _get_provider(self):
        api_key = config.get_api_key()
        if not api_key and config.provider != "ollama":
            raise ProviderError(
                f"No API key set for provider '{config.provider}'. "
                "Use /config to set your API key."
            )
        info = config.get_provider_info()
        return create_provider(
            config.provider, api_key, config.model,
            timeout=int(config.get("request_timeout", 60)),
            max_retries=int(config.get("max_retries", 2)),
            base_url_override=info.get("base_url"),
        )

    def _build_system(self) -> str:
        # Plain .replace() instead of .format(): the prompt template
        # contains literal JSON braces in its fallback example, and any
        # future edit that reintroduces unescaped {...} would silently
        # break every single chat call if .format() were used here again.
        return (SYSTEM_PROMPT
                .replace("{tools}", TOOL_SUMMARY)
                .replace("{workspace}", config.workspace))

    def _parse_tool_calls(self, text: str) -> List[Dict]:
        """Extract <tool_call>...</tool_call> blocks from AI response."""
        calls = []
        pattern = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
        for match in pattern.finditer(text):
            raw = match.group(1).strip()
            try:
                obj = json.loads(raw)
                if "tool" in obj:
                    calls.append(obj)
            except json.JSONDecodeError:
                # Try to extract anyway
                tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', raw)
                params_match = re.search(r'"params"\s*:\s*(\{[^}]*\})', raw, re.DOTALL)
                if tool_match:
                    tool_name = tool_match.group(1)
                    params = {}
                    if params_match:
                        try:
                            params = json.loads(params_match.group(1))
                        except Exception:
                            pass
                    calls.append({"tool": tool_name, "params": params})
        return calls

    def _list_models_tool(self, provider: Optional[str], free_only: bool, refresh: bool) -> ToolResult:
        """Live model listing for the AI itself to consult (e.g. when asked
        to recommend a cheaper/free model)."""
        try:
            models, source = config.get_live_models(provider, force_refresh=refresh)
            if free_only:
                models = [m for m in models if m.is_free]
            lines = ["[Source: %s]" % source]
            for m in models[:60]:
                lines.append("  %s | ctx=%s | %s" % (m.id, m.context_label(), m.price_label()))
            if len(models) > 60:
                lines.append("  ... and %d more" % (len(models) - 60))
            return ToolResult(True, "\n".join(lines))
        except Exception as e:
            return ToolResult(False, "", str(e))

    def run_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """Public entry point for running a single tool directly, without
        going through the chat loop (used by the web UI's file browser,
        and available for any other external caller)."""
        return self._execute_tool(tool_name, params)

    def _execute_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """Execute a named tool with given parameters."""
        if tool_name in getattr(self, "_excluded_tools", set()):
            return ToolResult(False, "", f"Tool '{tool_name}' is disabled for this session.")

        ws = config.workspace
        safe = config.get("safe_mode", True)

        dispatch = {
            "read_file": lambda p: read_file(p["path"], ws),
            "write_file": lambda p: write_file(p["path"], p["content"], ws),
            "edit_file": lambda p: edit_file(p["path"], p["old_text"], p["new_text"], ws),
            "patch_lines": lambda p: patch_lines(p["path"], int(p["start_line"]), int(p["end_line"]), p["new_content"], ws),
            "append_file": lambda p: append_file(p["path"], p["content"], ws),
            "delete_file": lambda p: delete_file(p["path"], ws),
            "move_file": lambda p: move_file(p["src"], p["dst"], ws),
            "copy_file": lambda p: copy_file(p["src"], p["dst"], ws),
            "create_directory": lambda p: create_directory(p["path"], ws),
            "list_directory": lambda p: list_directory(p.get("path", "."), ws, p.get("show_hidden", False)),
            "search_files": lambda p: search_files(p["pattern"], p.get("path", "."), ws, p.get("content", False)),
            "grep_file": lambda p: grep_file(p["path"], p["pattern"], ws, p.get("is_regex", False)),
            "run_command": lambda p: run_command(p["cmd"], ws, int(p.get("timeout", 60)), safe),
            "run_python": lambda p: run_python(p["code"], ws, safe),
            "git_status": lambda p: git_status(ws),
            "git_diff": lambda p: git_diff(ws, p.get("file", "")),
            "git_log": lambda p: git_log(ws, int(p.get("n", 10))),
            "git_add": lambda p: git_add(p.get("files", "."), ws),
            "git_commit": lambda p: git_commit(p["message"], ws),
            "git_init": lambda p: git_init(ws),
            "git_branch": lambda p: git_branch(ws),
            "git_checkout": lambda p: git_checkout(p["branch"], ws, bool(p.get("create", False))),
            "analyze_project": lambda p: analyze_project(ws),
            "get_file_info": lambda p: get_file_info(p["path"], ws),
            "read_file_lines": lambda p: read_file_lines(p["path"], int(p["start_line"]), int(p["end_line"]), ws),
            "head_file": lambda p: head_file(p["path"], int(p.get("n", 20)), ws),
            "tail_file": lambda p: tail_file(p["path"], int(p.get("n", 20)), ws),
            "count_lines": lambda p: count_lines(p["path"], ws),
            "disk_usage": lambda p: disk_usage(p.get("path", "."), ws),
            "env_info": lambda p: env_info(),
            "find_replace_in_files": lambda p: find_replace_in_files(
                p["pattern"], p["replacement"], p.get("file_glob", "*"), ws, bool(p.get("dry_run", True))
            ),
            "which": lambda p: which(p["name"]),
            "list_models": lambda p: self._list_models_tool(
                p.get("provider"), bool(p.get("free_only", False)), bool(p.get("refresh", False))
            ),
        }

        fn = dispatch.get(tool_name)
        if fn is None:
            return ToolResult(False, "", f"Unknown tool: {tool_name}")
        try:
            return fn(params)
        except KeyError as e:
            return ToolResult(False, "", f"Missing parameter: {e}")
        except Exception as e:
            return ToolResult(False, "", f"Tool error: {e}")

    def chat_stream(self, user_input: str, excluded_tools: Optional[set] = None) -> Iterator[Tuple[str, str]]:
        """
        Stream a response. Yields (type, content) tuples:
          ("text", chunk)       - AI text
          ("tool_call", name)   - tool being called
          ("tool_result", out)  - tool output
          ("error", msg)        - error
          ("done", "")          - finished

        Uses native provider function-calling (OpenAI-style tools= for
        OpenRouter/Groq/OpenAI/Ollama, Anthropic's own tool format for
        Anthropic) when the provider supports it — far more reliable than
        asking the model to emit a specific text pattern. Falls back to the
        legacy <tool_call> text-parsing only for providers/models that don't
        support native tools or that ignore them and answer in plain text.
        Runs a real multi-turn loop: tool results are fed back to the model
        so it can react to them, up to a safety cap on iterations.
        """
        self.messages.append({"role": "user", "content": user_input})

        sys_msgs = [{"role": "system", "content": self._build_system()}]

        try:
            provider = self._get_provider()
        except ProviderError as e:
            yield ("error", str(e))
            return

        native = getattr(provider, "supports_native_tools", False)
        is_anthropic = provider.__class__.__name__ == "AnthropicProvider"
        self._excluded_tools = excluded_tools or set()
        if native:
            from src.tools.file_tools import build_anthropic_tools_schema, build_openai_tools_schema
            tools_schema = build_anthropic_tools_schema() if is_anthropic else build_openai_tools_schema()
            if excluded_tools:
                if is_anthropic:
                    tools_schema = [t for t in tools_schema if t["name"] not in excluded_tools]
                else:
                    tools_schema = [t for t in tools_schema if t["function"]["name"] not in excluded_tools]
        else:
            tools_schema = None

        max_turns = 8  # safety cap against infinite tool-call loops
        for _turn in range(max_turns):
            all_msgs = sys_msgs + self.messages
            full_text = ""
            native_calls: List[Dict] = []

            try:
                stream = provider.chat(
                    all_msgs,
                    stream=True,
                    max_tokens=config.get("max_tokens", 4096),
                    temperature=config.get("temperature", 0.7),
                    tools=tools_schema,
                )
                for piece in stream:
                    if isinstance(piece, dict):
                        if piece.get("type") == "text":
                            full_text += piece["text"]
                            yield ("text", piece["text"])
                        elif piece.get("type") == "tool_calls":
                            native_calls = piece.get("tool_calls", [])
                    else:
                        # Defensive: a provider that still yields bare strings
                        full_text += piece
                        yield ("text", piece)
            except ProviderError as e:
                yield ("error", str(e))
                return
            except Exception as e:
                yield ("error", f"Unexpected error: {e}")
                return

            calls_to_run = []
            if native_calls:
                for c in native_calls:
                    calls_to_run.append({"id": c.get("id", ""), "tool": c.get("name", ""), "params": c.get("arguments", {})})
            else:
                # Fallback: legacy text-embedded <tool_call> blocks, for
                # models that ignore the native tools= parameter.
                for c in self._parse_tool_calls(full_text):
                    calls_to_run.append({"id": "", "tool": c.get("tool", ""), "params": c.get("params", {})})

            if not calls_to_run:
                self.messages.append({"role": "assistant", "content": full_text})
                yield ("done", "")
                return

            # Record the assistant turn that requested the tool call(s).
            if native_calls:
                if is_anthropic:
                    content_blocks = []
                    if full_text:
                        content_blocks.append({"type": "text", "text": full_text})
                    for c in native_calls:
                        content_blocks.append({
                            "type": "tool_use", "id": c.get("id", ""),
                            "name": c.get("name", ""), "input": c.get("arguments", {}),
                        })
                    self.messages.append({"role": "assistant", "content": content_blocks})
                else:
                    self.messages.append({
                        "role": "assistant",
                        "content": full_text or None,
                        "tool_calls": [
                            {"id": c.get("id", ""), "type": "function",
                             "function": {"name": c.get("name", ""), "arguments": json.dumps(c.get("arguments", {}))}}
                            for c in native_calls
                        ],
                    })
            else:
                self.messages.append({"role": "assistant", "content": full_text})

            tool_outputs = []
            for call in calls_to_run:
                tool_name = call["tool"]
                params = call["params"]

                if self._on_tool_call:
                    self._on_tool_call(tool_name, params)
                yield ("tool_call", tool_name)

                result = self._execute_tool(tool_name, params)
                result_str = str(result)

                if self._on_tool_result:
                    self._on_tool_result(tool_name, result)
                yield ("tool_result", result_str)
                tool_outputs.append((call["id"], tool_name, result_str))

            # Feed tool results back so the model can react to them.
            if native_calls:
                self._append_native_tool_results(tool_outputs, is_anthropic)
            else:
                summary = "\n".join(f"[Tool: {name}]\n{out}" for _id, name, out in tool_outputs)
                self.messages.append({"role": "user", "content": summary})

        yield ("error", "Stopped after too many tool-call turns (possible loop). "
                         "Try rephrasing your request.")

    def _append_native_tool_results(self, tool_outputs, is_anthropic: bool):
        """Append tool results to history in the format each native tool
        protocol expects, so the next turn's request is well-formed."""
        if is_anthropic:
            content = []
            for call_id, _name, out in tool_outputs:
                content.append({"type": "tool_result", "tool_use_id": call_id, "content": out})
            self.messages.append({"role": "user", "content": content})
        else:
            for call_id, name, out in tool_outputs:
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": out,
                })

    def chat_sync(self, user_input: str) -> str:
        """Non-streaming chat, returns full response string."""
        result_parts = []
        for typ, content in self.chat_stream(user_input):
            if typ in ("text", "tool_result", "error"):
                result_parts.append(content)
        return "".join(result_parts)

    def clear_history(self):
        self.messages.clear()

    def get_history(self) -> List[Dict]:
        return list(self.messages)

    def save_session(self, path: str):
        """Save conversation to a file."""
        import json as _json
        with open(path, "w", encoding="utf-8") as f:
            _json.dump({
                "messages": self.messages,
                "timestamp": time.time(),
                "provider": config.provider,
                "model": config.model,
            }, f, indent=2)

    def load_session(self, path: str):
        """Load conversation from a file."""
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        self.messages = data.get("messages", [])


# Global agent instance
agent = Agent()
