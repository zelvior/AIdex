#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIdex AI Coding Agent - Main Entry Point
Apache 2.0 License - See LICENSE file

Compatible with:
  - Windows XP, Vista, 7, 8, 10, 11 (32-bit and 64-bit)
  - Linux (any distro), macOS 10.9+
  - Python 2.7 and Python 3.x (full feature set needs 3.6+; a plain-text
    fallback UI runs on Python 2.7+ when modern dependencies are missing)

Usage:
    python aidex.py            Auto-detect best available interface
    python aidex.py --plain    Force the zero-dependency plain interface
    python aidex.py --full     Force the Rich/prompt_toolkit interface
                                (errors if those packages are unavailable)
"""

from __future__ import print_function
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def _want_plain():
    if "--plain" in sys.argv:
        return True
    if os.environ.get("AIDEX_PLAIN_TUI") == "1":
        return True
    return False


def _want_full():
    return "--full" in sys.argv


def _run_plain():
    from tui.plain import main as plain_main
    plain_main()


def _run_full():
    from tui.app import AIdexApp
    app = AIdexApp()
    app.run()


def main():
    forced_plain = _want_plain()
    forced_full = _want_full()

    if forced_full:
        _run_full()
        return

    if forced_plain:
        _run_plain()
        return

    # Auto-detect: try the full Rich/prompt_toolkit experience first.
    # This requires Python 3.7+ in practice. On anything older, or if the
    # packages are missing/broken, fall back to the plain stdlib-only UI
    # so AIdex still runs on Windows XP, 32-bit systems, and minimal
    # Python installs.
    if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 7):
        _run_plain()
        return

    try:
        import rich  # noqa: F401
        import prompt_toolkit  # noqa: F401
    except ImportError:
        _run_plain()
        return

    try:
        _run_full()
    except Exception as e:
        # If the rich UI crashes for any environment-specific reason
        # (unsupported console, missing terminal features on old Windows,
        # etc.), don't just die — degrade gracefully.
        sys.stderr.write("Full interface failed (%s); falling back to plain mode.\n" % e)
        _run_plain()


if __name__ == "__main__":
    main()
