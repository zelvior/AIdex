#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus Agent Core - Orchestrates AI model + tool execution
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
    git_status, git_diff, git_log, git_add, git_commit, git_init,
    analyze_project, get_file_info, TOOL_DEFINITIONS, ToolResult
)


SYSTEM_PROMPT = """You are Nexus, a professional AI coding agent. You help users with:
- Writing, editing, refactoring, and debugging code
- Managing files and directories
- Running commands and scripts
- Analyzing project structure
- Git operations
- Explaining code and concepts

## Tool Usage
When you need to perform file operations, run commands, or use any tools, output them in this EXACT format:

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
        if not api_key:
            raise ProviderError(
                f"No API key set for provider '{config.provider}'. "
                "Use /config to set your API key."
            )
        return create_provider(config.provider, api_key, config.model)

    def _build_system(self) -> str:
        return SYSTEM_PROMPT.format(
            tools=TOOL_SUMMARY,
            workspace=config.workspace,
        )

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

    def _execute_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """Execute a named tool with given parameters."""
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
            "run_python": lambda p: run_python(p["code"], ws),
            "git_status": lambda p: git_status(ws),
            "git_diff": lambda p: git_diff(ws, p.get("file", "")),
            "git_log": lambda p: git_log(ws, int(p.get("n", 10))),
            "git_add": lambda p: git_add(p.get("files", "."), ws),
            "git_commit": lambda p: git_commit(p["message"], ws),
            "git_init": lambda p: git_init(ws),
            "analyze_project": lambda p: analyze_project(ws),
            "get_file_info": lambda p: get_file_info(p["path"], ws),
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

    def chat_stream(self, user_input: str) -> Iterator[Tuple[str, str]]:
        """
        Stream a response. Yields (type, content) tuples:
          ("text", chunk)       - AI text
          ("tool_call", name)   - tool being called
          ("tool_result", out)  - tool output
          ("error", msg)        - error
          ("done", "")          - finished
        """
        self.messages.append({"role": "user", "content": user_input})

        sys_msgs = [{"role": "system", "content": self._build_system()}]
        all_msgs = sys_msgs + self.messages

        try:
            provider = self._get_provider()
        except ProviderError as e:
            yield ("error", str(e))
            return

        # Collect full AI response (streaming)
        full_response = ""
        try:
            stream = provider.chat(
                all_msgs,
                stream=True,
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.7),
            )
            for chunk in stream:
                full_response += chunk
                yield ("text", chunk)
        except ProviderError as e:
            yield ("error", str(e))
            return
        except Exception as e:
            yield ("error", f"Unexpected error: {e}")
            return

        # Parse and execute tool calls
        tool_calls = self._parse_tool_calls(full_response)
        tool_results_text = ""

        for call in tool_calls:
            tool_name = call.get("tool", "")
            params = call.get("params", {})

            if self._on_tool_call:
                self._on_tool_call(tool_name, params)
            yield ("tool_call", tool_name)

            result = self._execute_tool(tool_name, params)
            result_str = str(result)

            if self._on_tool_result:
                self._on_tool_result(tool_name, result)
            yield ("tool_result", result_str)
            tool_results_text += f"\n[Tool: {tool_name}]\n{result_str}\n"

        # Add assistant message to history
        final_content = full_response
        if tool_results_text:
            final_content += tool_results_text

        self.messages.append({
            "role": "assistant",
            "content": final_content
        })

        yield ("done", "")

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
