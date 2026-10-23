from importlib.metadata import version

import image_studio


def test_version_viene_de_pyproject():
    assert image_studio.__version__ == version("image-studio") == "0.1.0"
