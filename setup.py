#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIdex AI Coding Agent - Setup
Apache 2.0 License
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="aidex-agent",
    version="1.1.0",
    description="Professional CLI AI Coding Agent — OpenRouter, Groq, Anthropic, OpenAI, Ollama",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Zelvior",
    license="Apache-2.0",
    python_requires=">=2.7",
    packages=find_packages(),
    install_requires=[],
    extras_require={
        "full": [
            "rich>=10.0.0",
            "prompt_toolkit>=3.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aidex=aidex:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Terminals",
    ],
    keywords="ai coding agent cli terminal openrouter groq anthropic openai ollama llm",
    project_urls={
        "Source": "https://github.com/Zelvior/AIdex",
        "Bug Reports": "https://github.com/Zelvior/AIdex/issues",
    },
)
