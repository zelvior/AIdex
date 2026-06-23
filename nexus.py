#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus AI Coding Agent - Main Entry Point
Apache 2.0 License - See LICENSE file
"""

from __future__ import annotations
import sys
import os

# Ensure minimum Python version (2.7+ compatible imports where possible)
if sys.version_info < (3, 6):
    print("ERROR: Nexus requires Python 3.6 or higher.")
    print("Please upgrade your Python installation.")
    sys.exit(1)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from tui.app import NexusApp

def main():
    app = NexusApp()
    app.run()

if __name__ == "__main__":
    main()
