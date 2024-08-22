import os
import toml

with open("pyproject.toml", "r") as f:
        pyproject_data = toml.load(f)
VERSION = pyproject_data["tool"]["poetry"]["version"]

__version__ = VERSION

if __name__ == '__main__':
    os.environ['VERSION'] = VERSION
    print(VERSION)
