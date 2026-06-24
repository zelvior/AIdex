#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus AI Coding Agent - Legacy Entry Point
Apache 2.0 License - See LICENSE file

This project was renamed to AIdex. This file is kept for backward
compatibility so existing scripts, shortcuts, and muscle memory keep
working — it simply forwards to aidex.py.

Prefer running `python aidex.py` directly going forward.
"""

from __future__ import print_function
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aidex import main  # noqa: E402

if __name__ == "__main__":
    main()
