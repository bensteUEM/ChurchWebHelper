import importlib.util
import tomli_w

# Load the version number from version.py
spec = importlib.util.spec_from_file_location("version", "version.py")
version_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_module)
version = version_module.__version__

# Define the pyproject.toml content with the version
pyproject_toml_content = {
    "tool": {
        "poetry": {
            "name": "church-web-helper",
            "version": version,
            "description": "A python package to make use of ChurchTools API and Communi API with a docker packaged WebUI",
            "authors": ["bensteUEM"],
            "homepage": "https://github.com/bensteUEM/ChurchWebHelper",
            "license": "CC-BY-SA",
            "readme": "README.md",
            "include": ["templates/*.html", "static/*"],
            "dependencies": {
                "python": "^3.12",
                "churchtools-api": {
                    "git": "https://github.com/bensteUEM/ChurchToolsAPI.git",
                    "branch": "master",
                },
                "communi-api": {
                    "git": "https://github.com/bensteUEM/CommuniAPI.git",
                    "branch": "master",
                },
                "Flask": "^2.3.2",
                "Flask-Session": "^0.5.0",
                "requests": "^2.31.0",
                "python-docx": "^0.8.11",
                "gunicorn": "^22.0.0",
                "python-dotenv": "^1.0.0",
                "matplotlib": "^3.9.1",
                "pandas": "^2.2.2",
                "toml": "^0.10.2",
                "vobject" : "^0.9.8",
            },
            "group": {
                "dev": {
                    "dependencies": {
                        "poetry": "^1.6.1",
                        "tomli_w": "^1.0.0",
                        "wheel": "^0.41.2",
                        "setuptools": "^66.1.1",
                        "autopep8": "^2.0.4",
                    }
                }
            },
        }
    },
    "build-system": {
        "requires": ["poetry-core"],
        "build-backend": "poetry.core.masonry.api",
    },
}

with open("pyproject.toml", "wb") as toml_file:
    tomli_w.dump(pyproject_toml_content, toml_file)
