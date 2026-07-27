"""Dependency installer for TagComplete Neo Multi-CSV.

Forge and Forge Neo normally provide requests, FastAPI, and Gradio. PyYAML is
installed only when missing because YAML wildcard support depends on it.
"""

import importlib
import subprocess
import sys

REQUIRED_PACKAGES = [("yaml", "pyyaml")]


def install(package: str) -> None:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", package, "--quiet"],
        stdout=subprocess.DEVNULL,
    )


def check_and_install() -> None:
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"[TagComplete Neo Multi-CSV] Installing missing dependency: {pip_name}")
            install(pip_name)
            print(f"[TagComplete Neo Multi-CSV] {pip_name} installed successfully.")


check_and_install()
