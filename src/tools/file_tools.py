#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex File Tools - File system operations, shell execution, search, etc.
Apache 2.0 License
"""

from __future__ import annotations
import os
import re
import sys
import glob
import shutil
import fnmatch
import subprocess
import platform
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class ToolResult:
    def __init__(self, success: bool, output: str, error: str = ""):
        self.success = success
        self.output = output
        self.error = error

    def __str__(self):
        if self.success:
            return self.output
        return f"ERROR: {self.error}\n{self.output}"


# ─── FILE TOOLS ──────────────────────────────────────────────────────────────

def read_file(path: str, workspace: str = ".") -> ToolResult:
    """Read a file's contents, formatted with line numbers for AI/terminal
    display. Do NOT use this for round-tripping into an editable UI — the
    line-number prefixes and header are display formatting, not file
    content; saving that text back would corrupt the file. Use
    read_file_raw() for that instead."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        if os.path.getsize(full) > 5 * 1024 * 1024:  # 5MB limit
            return ToolResult(False, "", f"File too large (>5MB): {path}")
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        return ToolResult(True, f"[File: {path}] ({len(lines)} lines)\n{numbered}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def read_file_raw(path: str, workspace: str = ".") -> ToolResult:
    """Read a file's exact raw contents with no formatting, header, or
    line numbers added — safe to load into an editable text box and save
    straight back. Used by the web UI's file viewer/editor."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        if not os.path.isfile(full):
            return ToolResult(False, "", f"Not a file: {path}")
        if os.path.getsize(full) > 5 * 1024 * 1024:  # 5MB limit
            return ToolResult(False, "", f"File too large (>5MB): {path}")
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return ToolResult(True, content)
    except Exception as e:
        return ToolResult(False, "", str(e))


def write_file(path: str, content: str, workspace: str = ".") -> ToolResult:
    """Write/create a file."""
    try:
        full = _resolve(path, workspace)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        size = os.path.getsize(full)
        return ToolResult(True, f"✓ Written {path} ({size} bytes, {content.count(chr(10))+1} lines)")
    except Exception as e:
        return ToolResult(False, "", str(e))


def append_file(path: str, content: str, workspace: str = ".") -> ToolResult:
    """Append to a file."""
    try:
        full = _resolve(path, workspace)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(True, f"✓ Appended to {path}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def edit_file(path: str, old_text: str, new_text: str, workspace: str = ".") -> ToolResult:
    """Replace specific text in a file (like str_replace)."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        count = content.count(old_text)
        if count == 0:
            return ToolResult(False, "", f"Text not found in {path}")
        if count > 1:
            return ToolResult(False, "", f"Ambiguous: text appears {count} times in {path}")
        new_content = content.replace(old_text, new_text, 1)
        # Show diff
        diff = list(difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}", n=3
        ))
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
        diff_str = "".join(diff[:50])  # Limit diff output
        return ToolResult(True, f"✓ Edited {path}\n{diff_str}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def patch_lines(path: str, start_line: int, end_line: int, new_content: str, workspace: str = ".") -> ToolResult:
    """Replace lines start_line..end_line (1-indexed, inclusive) with new_content."""
    try:
        full = _resolve(path, workspace)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        s, e = max(0, start_line - 1), min(len(lines), end_line)
        new_lines = new_content.splitlines(keepends=True)
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        lines[s:e] = new_lines
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
        return ToolResult(True, f"✓ Patched lines {start_line}-{end_line} in {path}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def delete_file(path: str, workspace: str = ".") -> ToolResult:
    """Delete a file or empty directory."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"Not found: {path}")
        if os.path.isfile(full):
            os.remove(full)
            return ToolResult(True, f"✓ Deleted file: {path}")
        elif os.path.isdir(full):
            shutil.rmtree(full)
            return ToolResult(True, f"✓ Deleted directory: {path}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def move_file(src: str, dst: str, workspace: str = ".") -> ToolResult:
    """Move/rename a file or directory."""
    try:
        full_src = _resolve(src, workspace)
        full_dst = _resolve(dst, workspace)
        os.makedirs(os.path.dirname(full_dst), exist_ok=True)
        shutil.move(full_src, full_dst)
        return ToolResult(True, f"✓ Moved {src} → {dst}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def copy_file(src: str, dst: str, workspace: str = ".") -> ToolResult:
    """Copy a file."""
    try:
        full_src = _resolve(src, workspace)
        full_dst = _resolve(dst, workspace)
        os.makedirs(os.path.dirname(full_dst), exist_ok=True)
        shutil.copy2(full_src, full_dst)
        return ToolResult(True, f"✓ Copied {src} → {dst}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def create_directory(path: str, workspace: str = ".") -> ToolResult:
    """Create a directory (and parents)."""
    try:
        full = _resolve(path, workspace)
        os.makedirs(full, exist_ok=True)
        return ToolResult(True, f"✓ Created directory: {path}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def list_directory(path: str = ".", workspace: str = ".", show_hidden: bool = False) -> ToolResult:
    """List directory contents in a tree-like format."""
    try:
        full = _resolve(path, workspace)
        if not os.path.isdir(full):
            return ToolResult(False, "", f"Not a directory: {path}")
        lines = [f"📁 {path}/"]
        entries = sorted(os.scandir(full), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir():
                lines.append(f"  📁 {entry.name}/")
                try:
                    sub = sorted(os.scandir(entry.path), key=lambda e: (not e.is_dir(), e.name.lower()))
                    for sub_entry in sub[:20]:  # Limit depth
                        if not show_hidden and sub_entry.name.startswith("."):
                            continue
                        icon = "📁" if sub_entry.is_dir() else "📄"
                        lines.append(f"    {icon} {sub_entry.name}")
                    if len(list(os.scandir(entry.path))) > 20:
                        lines.append(f"    ... (truncated)")
                except PermissionError:
                    lines.append(f"    [Permission denied]")
            else:
                size = _human_size(entry.stat().st_size)
                lines.append(f"  📄 {entry.name} ({size})")
        return ToolResult(True, "\n".join(lines))
    except Exception as e:
        return ToolResult(False, "", str(e))


def list_directory_flat(path: str = ".", workspace: str = ".", show_hidden: bool = False):
    """Single-level, structured directory listing for UI consumption (the
    web file browser). Unlike list_directory(), this returns a plain list
    of dicts rather than a pre-rendered text tree, so a frontend can render
    and navigate it without parsing emoji-prefixed text lines."""
    try:
        full = _resolve(path, workspace)
        if not os.path.isdir(full):
            return ToolResult(False, "", f"Not a directory: {path}"), []
        entries = sorted(os.scandir(full), key=lambda e: (not e.is_dir(), e.name.lower()))
        items = []
        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue
            is_dir = entry.is_dir()
            item = {"name": entry.name, "is_dir": is_dir}
            if not is_dir:
                try:
                    item["size"] = entry.stat().st_size
                except OSError:
                    item["size"] = 0
            items.append(item)
        return ToolResult(True, f"{len(items)} entries"), items
    except Exception as e:
        return ToolResult(False, "", str(e)), []


def search_files(pattern: str, path: str = ".", workspace: str = ".", content: bool = False) -> ToolResult:
    """Search for files by name pattern or content."""
    try:
        full = _resolve(path, workspace)
        results = []
        for root, dirs, files in os.walk(full):
            # Skip common ignore dirs
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next"}]
            for fname in files:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, full)
                if fnmatch.fnmatch(fname.lower(), pattern.lower()) or fnmatch.fnmatch(rel.lower(), pattern.lower()):
                    results.append(rel)
                elif content:
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read(100_000)
                        if pattern.lower() in text.lower():
                            # Find matching lines
                            for i, line in enumerate(text.splitlines(), 1):
                                if pattern.lower() in line.lower():
                                    results.append(f"{rel}:{i}: {line.strip()[:80]}")
                    except Exception:
                        pass
        if not results:
            return ToolResult(True, f"No results for '{pattern}'")
        return ToolResult(True, f"Found {len(results)} result(s) for '{pattern}':\n" + "\n".join(results[:100]))
    except Exception as e:
        return ToolResult(False, "", str(e))


def grep_file(path: str, pattern: str, workspace: str = ".", is_regex: bool = False) -> ToolResult:
    """Search for pattern in a file."""
    try:
        full = _resolve(path, workspace)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        results = []
        for i, line in enumerate(lines, 1):
            if is_regex:
                if re.search(pattern, line):
                    results.append(f"{i:4d}: {line.rstrip()}")
            else:
                if pattern.lower() in line.lower():
                    results.append(f"{i:4d}: {line.rstrip()}")
        if not results:
            return ToolResult(True, f"Pattern '{pattern}' not found in {path}")
        return ToolResult(True, f"[{path}] {len(results)} match(es):\n" + "\n".join(results[:50]))
    except Exception as e:
        return ToolResult(False, "", str(e))


# ─── SHELL / EXECUTION ───────────────────────────────────────────────────────

def run_command(cmd: str, workspace: str = ".", timeout: int = 60, safe_mode: bool = True) -> ToolResult:
    """Execute a shell command."""
    DANGEROUS = ["rm -rf /", "format", "mkfs", "dd if=", ":(){:|:&};:", "sudo rm -rf"]
    if safe_mode:
        for danger in DANGEROUS:
            if danger.lower() in cmd.lower():
                return ToolResult(False, "", f"Blocked dangerous command: {danger}")
    try:
        full_wd = os.path.abspath(workspace)
        is_win = platform.system() == "Windows"
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=full_wd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            return ToolResult(False, output, f"Exit code: {result.returncode}")
        return ToolResult(True, output or "(no output)")
    except subprocess.TimeoutExpired:
        return ToolResult(False, "", f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(False, "", str(e))


def run_python(code: str, workspace: str = ".", safe_mode: bool = True) -> ToolResult:
    """Execute Python code snippet."""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        result = run_command(f"{sys.executable} {tmp}", workspace=workspace, timeout=30, safe_mode=safe_mode)
        try:
            os.unlink(tmp)
        except Exception:
            pass
        return result
    except Exception as e:
        return ToolResult(False, "", str(e))


# ─── GIT TOOLS ───────────────────────────────────────────────────────────────

def git_status(workspace: str = ".") -> ToolResult:
    return run_command("git status", workspace)

def git_diff(workspace: str = ".", file: str = "") -> ToolResult:
    cmd = f"git diff {file}".strip()
    return run_command(cmd, workspace)

def git_log(workspace: str = ".", n: int = 10) -> ToolResult:
    return run_command(f"git log --oneline -n {n}", workspace)

def git_add(files: str = ".", workspace: str = ".") -> ToolResult:
    return run_command(f"git add {files}", workspace)

def git_commit(message: str, workspace: str = ".") -> ToolResult:
    return run_command(f'git commit -m "{message}"', workspace)

def git_init(workspace: str = ".") -> ToolResult:
    return run_command("git init", workspace)

def git_branch(workspace: str = ".") -> ToolResult:
    return run_command("git branch -a", workspace)

def git_checkout(branch: str, workspace: str = ".", create: bool = False) -> ToolResult:
    flag = "-b " if create else ""
    return run_command(f"git checkout {flag}{branch}", workspace)


# ─── PROJECT ANALYSIS ────────────────────────────────────────────────────────

def analyze_project(workspace: str = ".") -> ToolResult:
    """Analyze project structure and return summary."""
    try:
        lines = ["=== Project Analysis ===\n"]

        # Count files by extension
        ext_count: Dict[str, int] = {}
        total_lines = 0
        total_files = 0
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", "dist", "build"}]
            for f in files:
                total_files += 1
                ext = os.path.splitext(f)[1].lower() or "(no ext)"
                ext_count[ext] = ext_count.get(ext, 0) + 1
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        total_lines += sum(1 for _ in fp)
                except Exception:
                    pass

        lines.append(f"Total files: {total_files}")
        lines.append(f"Total lines: {total_lines}")
        lines.append("\nFile types:")
        for ext, cnt in sorted(ext_count.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {ext:15s} {cnt:4d}")

        # Detect project type
        project_type = _detect_project_type(workspace)
        lines.append(f"\nProject type: {project_type}")

        # Key files
        key_files = ["package.json", "pyproject.toml", "setup.py", "requirements.txt",
                     "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Makefile",
                     "Dockerfile", ".env.example", "README.md"]
        found_key = [f for f in key_files if os.path.exists(os.path.join(workspace, f))]
        if found_key:
            lines.append(f"\nKey files: {', '.join(found_key)}")

        return ToolResult(True, "\n".join(lines))
    except Exception as e:
        return ToolResult(False, "", str(e))


def _detect_project_type(workspace: str) -> str:
    checks = [
        ("package.json", "Node.js/JavaScript"),
        ("pyproject.toml", "Python (pyproject)"),
        ("setup.py", "Python"),
        ("requirements.txt", "Python"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("pom.xml", "Java/Maven"),
        ("build.gradle", "Java/Gradle"),
        ("*.csproj", "C#/.NET"),
        ("CMakeLists.txt", "C/C++"),
        ("Gemfile", "Ruby"),
        ("composer.json", "PHP"),
    ]
    for fname, ptype in checks:
        if "*" in fname:
            if glob.glob(os.path.join(workspace, fname)):
                return ptype
        elif os.path.exists(os.path.join(workspace, fname)):
            return ptype
    return "Unknown"


def get_file_info(path: str, workspace: str = ".") -> ToolResult:
    """Get metadata about a file."""
    try:
        full = _resolve(path, workspace)
        stat = os.stat(full)
        import time as _time
        info = [
            f"Path:     {path}",
            f"Size:     {_human_size(stat.st_size)}",
            f"Modified: {_time.ctime(stat.st_mtime)}",
            f"Created:  {_time.ctime(stat.st_ctime)}",
            f"Type:     {'Directory' if os.path.isdir(full) else 'File'}",
        ]
        if os.path.isfile(full):
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                info.append(f"Lines:    {len(lines)}")
            except Exception:
                pass
        return ToolResult(True, "\n".join(info))
    except Exception as e:
        return ToolResult(False, "", str(e))


# ─── ADDITIONAL READ/INSPECT TOOLS (low-memory friendly) ────────────────────

def read_file_lines(path: str, start_line: int, end_line: int, workspace: str = ".") -> ToolResult:
    """Read only a specific line range from a file (avoids loading huge files fully)."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        out = []
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if i > end_line:
                    break
                if i >= start_line:
                    out.append(f"{i:4d} | {line.rstrip(chr(10))}")
        if not out:
            return ToolResult(False, "", f"No lines in range {start_line}-{end_line}")
        return ToolResult(True, f"[File: {path}] lines {start_line}-{end_line}\n" + "\n".join(out))
    except Exception as e:
        return ToolResult(False, "", str(e))


def head_file(path: str, n: int = 20, workspace: str = ".") -> ToolResult:
    """Read the first N lines of a file without loading the whole file into memory."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        out = []
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if i > n:
                    break
                out.append(f"{i:4d} | {line.rstrip(chr(10))}")
        return ToolResult(True, f"[File: {path}] first {len(out)} line(s)\n" + "\n".join(out))
    except Exception as e:
        return ToolResult(False, "", str(e))


def tail_file(path: str, n: int = 20, workspace: str = ".") -> ToolResult:
    """Read the last N lines of a file using a bounded-memory ring buffer
    (safe on low-RAM/32-bit devices even for large files)."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        from collections import deque
        buf = deque(maxlen=max(1, n))
        total = 0
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                buf.append(line.rstrip("\n"))
                total += 1
        start_no = total - len(buf) + 1
        out = [f"{start_no + i:4d} | {line}" for i, line in enumerate(buf)]
        return ToolResult(True, f"[File: {path}] last {len(out)} line(s) (of {total})\n" + "\n".join(out))
    except Exception as e:
        return ToolResult(False, "", str(e))


def count_lines(path: str, workspace: str = ".") -> ToolResult:
    """Count lines/words/chars in a file without holding it fully in memory."""
    try:
        full = _resolve(path, workspace)
        if not os.path.exists(full):
            return ToolResult(False, "", f"File not found: {path}")
        lines = words = chars = 0
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                lines += 1
                words += len(line.split())
                chars += len(line)
        return ToolResult(True, f"[File: {path}] lines={lines} words={words} chars={chars}")
    except Exception as e:
        return ToolResult(False, "", str(e))


def disk_usage(path: str = ".", workspace: str = ".") -> ToolResult:
    """Report disk usage for a path (free/used/total), and directory size."""
    try:
        full = _resolve(path, workspace)
        usage = shutil.disk_usage(full if os.path.exists(full) else workspace)
        lines = [
            f"Disk for: {path}",
            f"  Total: {_human_size(usage.total)}",
            f"  Used:  {_human_size(usage.used)}",
            f"  Free:  {_human_size(usage.free)}",
        ]
        if os.path.isdir(full):
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(full):
                dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", "venv"}]
                for fname in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, fname))
                        file_count += 1
                    except OSError:
                        pass
            lines.append(f"\nDirectory size: {_human_size(total_size)} ({file_count} files)")
        return ToolResult(True, "\n".join(lines))
    except Exception as e:
        return ToolResult(False, "", str(e))


def env_info() -> ToolResult:
    """Report Python/OS/hardware info — useful for diagnosing low-end or unusual systems."""
    try:
        import sys as _sys
        bits = "64-bit" if _sys.maxsize > 2**32 else "32-bit"
        lines = [
            f"Python:    {_sys.version.split()[0]} ({bits} build)",
            f"OS:        {platform.system()} {platform.release()} ({platform.version()})",
            f"Machine:   {platform.machine()}",
            f"Processor: {platform.processor() or 'unknown'}",
        ]
        try:
            import os as _os
            cpu_count = _os.cpu_count() or 1
            lines.append(f"CPU cores: {cpu_count}")
        except Exception:
            pass
        return ToolResult(True, "\n".join(lines))
    except Exception as e:
        return ToolResult(False, "", str(e))


def find_replace_in_files(pattern: str, replacement: str, file_glob: str = "*",
                           workspace: str = ".", dry_run: bool = True) -> ToolResult:
    """Find and replace plain text across files matching a glob (recursive).
    dry_run=True (default) only reports matches without modifying anything."""
    try:
        changed = []
        match_count = 0
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}]
            for fname in files:
                if not fnmatch.fnmatch(fname, file_glob):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, workspace)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                count = content.count(pattern)
                if count > 0:
                    match_count += count
                    changed.append(f"{rel}: {count} match(es)")
                    if not dry_run:
                        new_content = content.replace(pattern, replacement)
                        with open(fpath, "w", encoding="utf-8", newline="") as f:
                            f.write(new_content)
        if not changed:
            return ToolResult(True, f"No matches for '{pattern}'")
        mode = "DRY RUN (no files modified)" if dry_run else "APPLIED"
        return ToolResult(True, f"[{mode}] {match_count} total match(es) in {len(changed)} file(s):\n" + "\n".join(changed[:100]))
    except Exception as e:
        return ToolResult(False, "", str(e))


def which(name: str) -> ToolResult:
    """Locate an executable on PATH (cross-platform)."""
    try:
        found = shutil.which(name)
        if found:
            return ToolResult(True, found)
        return ToolResult(False, "", f"'{name}' not found on PATH")
    except Exception as e:
        return ToolResult(False, "", str(e))


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _resolve(path: str, workspace: str) -> str:
    """Resolve path relative to workspace, prevent traversal attacks."""
    if os.path.isabs(path):
        return os.path.normpath(path)
    resolved = os.path.normpath(os.path.join(os.path.abspath(workspace), path))
    return resolved


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ─── TOOL REGISTRY ───────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file with line numbers.",
        "parameters": {
            "path": "str - file path relative to workspace",
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with given content.",
        "parameters": {
            "path": "str - file path",
            "content": "str - file content",
        },
    },
    {
        "name": "edit_file",
        "description": "Replace specific text in a file (str_replace style). old_text must be unique.",
        "parameters": {
            "path": "str - file path",
            "old_text": "str - exact text to replace",
            "new_text": "str - replacement text",
        },
    },
    {
        "name": "patch_lines",
        "description": "Replace a range of lines in a file.",
        "parameters": {
            "path": "str - file path",
            "start_line": "int - first line (1-indexed)",
            "end_line": "int - last line (1-indexed, inclusive)",
            "new_content": "str - replacement content",
        },
    },
    {
        "name": "append_file",
        "description": "Append content to the end of a file.",
        "parameters": {
            "path": "str - file path",
            "content": "str - content to append",
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file or directory.",
        "parameters": {
            "path": "str - path to delete",
        },
    },
    {
        "name": "move_file",
        "description": "Move or rename a file/directory.",
        "parameters": {
            "src": "str - source path",
            "dst": "str - destination path",
        },
    },
    {
        "name": "copy_file",
        "description": "Copy a file.",
        "parameters": {
            "src": "str - source path",
            "dst": "str - destination path",
        },
    },
    {
        "name": "create_directory",
        "description": "Create a directory (and any missing parent directories).",
        "parameters": {
            "path": "str - directory path",
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory.",
        "parameters": {
            "path": "str - directory path (default: '.')",
        },
    },
    {
        "name": "search_files",
        "description": "Search for files by name pattern. Use content=true to search inside files.",
        "parameters": {
            "pattern": "str - glob pattern like '*.py' or search term",
            "path": "str - directory to search in (default: '.')",
            "content": "bool - search inside file contents (default: false)",
        },
    },
    {
        "name": "grep_file",
        "description": "Search for a pattern within a specific file.",
        "parameters": {
            "path": "str - file path",
            "pattern": "str - pattern to search",
            "is_regex": "bool - treat pattern as regex (default: false)",
        },
    },
    {
        "name": "run_command",
        "description": "Execute a shell command in the workspace directory.",
        "parameters": {
            "cmd": "str - command to run",
            "timeout": "int - max seconds (default: 60)",
        },
    },
    {
        "name": "run_python",
        "description": "Execute a Python code snippet.",
        "parameters": {
            "code": "str - Python code to execute",
        },
    },
    {
        "name": "git_status",
        "description": "Show git status of the workspace.",
        "parameters": {},
    },
    {
        "name": "git_diff",
        "description": "Show git diff (optionally for a specific file).",
        "parameters": {
            "file": "str - specific file to diff (optional)",
        },
    },
    {
        "name": "git_log",
        "description": "Show recent git commits.",
        "parameters": {
            "n": "int - number of commits (default: 10)",
        },
    },
    {
        "name": "git_add",
        "description": "Stage files for git commit.",
        "parameters": {
            "files": "str - files to stage (default: '.')",
        },
    },
    {
        "name": "git_commit",
        "description": "Commit staged changes.",
        "parameters": {
            "message": "str - commit message",
        },
    },
    {
        "name": "git_init",
        "description": "Initialize a new git repository.",
        "parameters": {},
    },
    {
        "name": "git_branch",
        "description": "List all git branches (local and remote).",
        "parameters": {},
    },
    {
        "name": "git_checkout",
        "description": "Switch (or create) a git branch.",
        "parameters": {
            "branch": "str - branch name",
            "create": "bool - create new branch (default: false)",
        },
    },
    {
        "name": "analyze_project",
        "description": "Analyze the project structure, file types, and detect project type.",
        "parameters": {},
    },
    {
        "name": "get_file_info",
        "description": "Get metadata about a file (size, dates, line count).",
        "parameters": {
            "path": "str - file path",
        },
    },
    {
        "name": "read_file_lines",
        "description": "Read only a specific line range of a file (memory-efficient for huge files).",
        "parameters": {
            "path": "str - file path",
            "start_line": "int - first line (1-indexed)",
            "end_line": "int - last line (1-indexed, inclusive)",
        },
    },
    {
        "name": "head_file",
        "description": "Read the first N lines of a file.",
        "parameters": {
            "path": "str - file path",
            "n": "int - number of lines (default: 20)",
        },
    },
    {
        "name": "tail_file",
        "description": "Read the last N lines of a file (memory-bounded, safe for huge files on low-RAM devices).",
        "parameters": {
            "path": "str - file path",
            "n": "int - number of lines (default: 20)",
        },
    },
    {
        "name": "count_lines",
        "description": "Count lines, words, and characters in a file.",
        "parameters": {
            "path": "str - file path",
        },
    },
    {
        "name": "disk_usage",
        "description": "Report disk free/used/total space and directory size.",
        "parameters": {
            "path": "str - path to check (default: '.')",
        },
    },
    {
        "name": "env_info",
        "description": "Report Python version, OS, CPU architecture (32/64-bit), and core count.",
        "parameters": {},
    },
    {
        "name": "find_replace_in_files",
        "description": "Find and replace plain text across files matching a glob pattern, recursively. Defaults to dry-run (preview only).",
        "parameters": {
            "pattern": "str - text to find",
            "replacement": "str - text to replace with",
            "file_glob": "str - glob pattern like '*.py' (default: '*')",
            "dry_run": "bool - preview only, don't modify files (default: true)",
        },
    },
    {
        "name": "which",
        "description": "Locate an executable on the system PATH.",
        "parameters": {
            "name": "str - executable name",
        },
    },
    {
        "name": "list_models",
        "description": "List currently available AI models for a provider, fetched live from the provider's API with real pricing and context length (cached for offline use).",
        "parameters": {
            "provider": "str - provider name (default: current provider)",
            "free_only": "bool - only show free models (default: false)",
            "refresh": "bool - force a fresh fetch, bypassing cache (default: false)",
        },
    },
]


# ─── NATIVE FUNCTION-CALLING SCHEMA ─────────────────────────────────────────
# Converts the compact TOOL_DEFINITIONS format above into real OpenAI-style
# JSON Schema, so providers that support native function/tool calling
# (OpenRouter, Groq, OpenAI, Ollama via OpenAI-compat, and Anthropic via its
# own tool format) get reliable, structured tool calls instead of relying on
# the model to emit a specific text pattern that has to be regex-parsed.

_TYPE_MAP = {"str": "string", "int": "integer", "float": "number",
             "bool": "boolean", "list": "array", "dict": "object"}


def _parse_param_spec(spec: str):
    """'str - file path' -> ('string', 'file path', required=True).
    A description containing 'default:' marks the param as optional."""
    if " - " in spec:
        type_part, desc = spec.split(" - ", 1)
    else:
        type_part, desc = spec, ""
    json_type = _TYPE_MAP.get(type_part.strip().lower(), "string")
    required = "default:" not in desc.lower()
    return json_type, desc.strip(), required


def build_openai_tools_schema():
    """Return TOOL_DEFINITIONS converted to OpenAI/Groq/OpenRouter-style
    function-calling tool schemas."""
    schemas = []
    for t in TOOL_DEFINITIONS:
        properties = {}
        required = []
        for pname, pspec in t["parameters"].items():
            json_type, desc, is_required = _parse_param_spec(pspec)
            properties[pname] = {"type": json_type, "description": desc}
            if is_required:
                required.append(pname)
        schemas.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return schemas


def build_anthropic_tools_schema():
    """Return TOOL_DEFINITIONS converted to Anthropic's native tool format
    (input_schema instead of nested function.parameters)."""
    schemas = []
    for t in TOOL_DEFINITIONS:
        properties = {}
        required = []
        for pname, pspec in t["parameters"].items():
            json_type, desc, is_required = _parse_param_spec(pspec)
            properties[pname] = {"type": json_type, "description": desc}
            if is_required:
                required.append(pname)
        schemas.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        })
    return schemas
