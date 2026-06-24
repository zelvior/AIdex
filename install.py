#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIdex AI Coding Agent — Universal Installer
Supports: Windows XP+ (32/64-bit), Linux, macOS
Apache 2.0 License

This installer never hard-fails on old systems. If your Python version
or platform can't support the Rich/prompt_toolkit dependencies, AIdex
will still run using its zero-dependency plain-text interface.
"""

from __future__ import print_function
import sys
import os
import subprocess
import platform

MIN_PYTHON_FOR_FULL_UI = (3, 7)
REQUIRED_PACKAGES = ["rich>=10.0.0", "prompt_toolkit>=3.0.0"]

BANNER = """
   ___    ____    __
  / _ |  /  _/___/ /__ __
 / __ | _/ // _  / -_) \\ /
/_/ |_|/___/\\_,_/\\__/_\\_\\

   AIdex AI Coding Agent — Installer v1.1.0
"""

def check_python():
    v = sys.version_info[:2]
    arch = platform.machine()
    bits = "64-bit" if sys.maxsize > 2 ** 32 else "32-bit"
    print("Python %d.%d OK (%s, %s)" % (v[0], v[1], arch, bits))
    if v < (2, 7):
        print("WARNING: Python is very old (<2.7). AIdex's plain UI needs 2.7+.")
        print("AIdex may not run correctly. Consider upgrading Python.")
    elif v < MIN_PYTHON_FOR_FULL_UI:
        print("Note: Python %d.%d is below %d.%d, the minimum for the full" %
              (v[0], v[1], MIN_PYTHON_FOR_FULL_UI[0], MIN_PYTHON_FOR_FULL_UI[1]))
        print("Rich/prompt_toolkit interface. AIdex will automatically use")
        print("its zero-dependency plain-text interface instead — this is")
        print("expected and fully supported (e.g. on Windows XP).")
    return v

def install_packages(py_version):
    if py_version < MIN_PYTHON_FOR_FULL_UI:
        print("Skipping rich/prompt_toolkit install (Python too old for them).")
        print("AIdex will run in plain mode, which needs no extra packages.")
        return

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
        print("Installing %s..." % pkg)
        try:
            r = subprocess.run(pip_cmd + [pkg], capture_output=True, text=True)
            if r.returncode != 0:
                print("  WARNING: Could not install %s: %s" % (pkg, r.stderr.strip()[:200]))
                print("  AIdex will still work using its plain-text fallback interface.")
            else:
                print("  OK: %s" % pkg)
        except Exception as e:
            print("  WARNING: Could not install %s: %s" % (pkg, e))
            print("  AIdex will still work using its plain-text fallback interface.")

def make_executable():
    """Make aidex.py (and legacy nexus.py) executable on Unix."""
    if platform.system() != "Windows":
        base = os.path.dirname(os.path.abspath(__file__))
        for fname in ("aidex.py", "nexus.py"):
            script = os.path.join(base, fname)
            if not os.path.exists(script):
                continue
            try:
                os.chmod(script, 0o755)
                print("Made %s executable" % fname)
            except Exception as e:
                print("Note: Could not chmod %s: %s" % (fname, e))

def create_launcher():
    """Create platform-specific launcher(s): aidex (primary) and a legacy
    nexus alias for anyone with old muscle memory or scripts."""
    base = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(base, "aidex.py")

    if platform.system() == "Windows":
        bat = os.path.join(base, "aidex.bat")
        with open(bat, "w") as f:
            f.write('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, script))
        print("Created launcher: %s" % bat)

        legacy_bat = os.path.join(base, "nexus.bat")
        with open(legacy_bat, "w") as f:
            f.write('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, script))
        print("Created legacy launcher: %s" % legacy_bat)
    else:
        sh = os.path.join(base, "aidex")
        with open(sh, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script))
        os.chmod(sh, 0o755)
        print("Created launcher: %s" % sh)

        legacy_sh = os.path.join(base, "nexus")
        with open(legacy_sh, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script))
        os.chmod(legacy_sh, 0o755)
        print("Created legacy launcher: %s" % legacy_sh)

def print_success():
    if platform.system() == "Windows":
        run_cmd = "aidex.bat"
    else:
        run_cmd = "python aidex.py  or  ./aidex"

    print("""
+--------------------------------------------+
|  AIdex installed successfully!            |
|                                            |
|  To start:                                 |
|    """ + run_cmd.ljust(38) + """|
|                                            |
|  Then type /config to set your AI key     |
|  Free: openrouter.ai, groq.com            |
|  Offline/local: ollama.com (no key)       |
+--------------------------------------------+
""")


def main():
    print(BANNER)
    print("Platform: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()))
    print()

    print("1/4 Checking Python version...")
    py_version = check_python()

    print("\n2/4 Installing dependencies...")
    install_packages(py_version)

    print("\n3/4 Setting up launcher...")
    make_executable()
    create_launcher()

    print("\n4/4 Done!")
    print_success()

if __name__ == "__main__":
    main()
