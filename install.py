#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus AI Coding Agent — Universal Installer
Supports: Windows 7+, Linux, macOS | 32-bit and 64-bit
Apache 2.0 License
"""

from __future__ import print_function
import sys
import os
import subprocess
import platform

REQUIRED_PYTHON = (3, 6)
REQUIRED_PACKAGES = ["rich>=10.0.0", "prompt_toolkit>=3.0.0"]

BANNER = """
  _   _                      _    ___
 | \\ | | _____  ___   _ ___ | |  / _ \\
 |  \\| |/ _ \\ \\/ / | | / __|| | | (_) |
 | |\\  |  __/>  <| |_| \\__ \\| |__\\__, |
 |_| \\_|\\___/_/\\_\\\\__,_|___/|____|  /_/

   AI Coding Agent — Installer v1.0.0
"""

def check_python():
    v = sys.version_info[:2]
    if v < REQUIRED_PYTHON:
        print(f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required, got {v[0]}.{v[1]}")
        sys.exit(1)
    arch = platform.machine()
    print(f"Python {v[0]}.{v[1]} OK ({arch})")

def install_packages():
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]

    # Add --break-system-packages for newer Debian/Ubuntu
    try:
        result = subprocess.run(
            pip_cmd + ["--dry-run", "rich"],
            capture_output=True, text=True
        )
        if "externally-managed" in result.stderr:
            pip_cmd.append("--break-system-packages")
    except Exception:
        pass

    for pkg in REQUIRED_PACKAGES:
        print(f"Installing {pkg}...")
        r = subprocess.run(pip_cmd + [pkg], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  WARNING: Could not install {pkg}: {r.stderr.strip()[:200]}")
        else:
            print(f"  OK: {pkg}")

def make_executable():
    """Make nexus.py executable on Unix."""
    if platform.system() != "Windows":
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus.py")
        try:
            os.chmod(script, 0o755)
            print("Made nexus.py executable")
        except Exception as e:
            print(f"Note: Could not chmod nexus.py: {e}")

def create_launcher():
    """Create platform-specific launcher."""
    base = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(base, "nexus.py")

    if platform.system() == "Windows":
        bat = os.path.join(base, "nexus.bat")
        with open(bat, "w") as f:
            f.write(f'@echo off\n"{sys.executable}" "{script}" %*\n')
        print(f"Created launcher: {bat}")
    else:
        sh = os.path.join(base, "nexus")
        with open(sh, "w") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        os.chmod(sh, 0o755)
        print(f"Created launcher: {sh}")

def print_success():
    base = os.path.dirname(os.path.abspath(__file__))
    if platform.system() == "Windows":
        run_cmd = f"nexus.bat"
    else:
        run_cmd = f"python3 nexus.py  or  ./nexus"

    print("""
╔══════════════════════════════════════════╗
║  Nexus installed successfully!           ║
║                                          ║
║  To start:                               ║
║    """ + run_cmd.ljust(38) + """║
║                                          ║
║  Then type /config to set your API key  ║
║  Free keys: openrouter.ai, groq.com     ║
╚══════════════════════════════════════════╝
""")

def main():
    print(BANNER)
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print()

    print("1/4 Checking Python version...")
    check_python()

    print("\n2/4 Installing dependencies...")
    install_packages()

    print("\n3/4 Setting up launcher...")
    make_executable()
    create_launcher()

    print("\n4/4 Done!")
    print_success()

if __name__ == "__main__":
    main()
