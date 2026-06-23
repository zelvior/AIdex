#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexus AI Coding Agent - Setup
Apache 2.0 License
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="nexus-agent",
    version="1.0.0",
    description="Professional CLI AI Coding Agent — OpenRouter, Groq, Anthropic, OpenAI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Nexus Contributors",
    license="Apache-2.0",
    python_requires=">=3.6",
    packages=find_packages(),
    install_requires=[
        "rich>=10.0.0",
        "prompt_toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nexus=nexus:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Terminals",
    ],
    keywords="ai coding agent cli terminal openrouter groq anthropic openai llm",
    project_urls={
        "Source": "https://github.com/nexus-agent",
        "Bug Reports": "https://github.com/nexus-agent/issues",
    },
)
