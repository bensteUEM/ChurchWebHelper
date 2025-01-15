"""Helper script which aids github actions to access version number."""

import os
from pathlib import Path

import toml

with Path("pyproject.toml").open() as f:
    pyproject_data = toml.load(f)
VERSION = pyproject_data["tool"]["poetry"]["version"]

__version__ = VERSION

if __name__ == "__main__":
    os.environ["VERSION"] = VERSION
    print(VERSION)  # noqa:T201
