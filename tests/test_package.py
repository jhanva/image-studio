import tomllib
from importlib.metadata import version
from pathlib import Path

import image_studio

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_viene_de_pyproject():
    esperada = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert image_studio.__version__ == version("image-studio") == esperada
