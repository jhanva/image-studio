"""Image Studio: suite de escritorio para manipular imágenes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("image-studio")
except PackageNotFoundError:
    __version__ = "0.0.0"
