"""Punto de entrada de ImageStudio.exe e image-studio-cli.exe (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _preparar_cuda(base: Path) -> None:
    # En el ejecutable no existe site-packages: las DLL de CUDA y cuDNN se copian a _internal
    # y se cargan desde ahí antes de crear sesiones de ONNX Runtime.
    import onnxruntime

    cuda = base / "nvidia" / "cu13" / "bin" / "x86_64"
    cudnn = base / "nvidia" / "cudnn" / "bin"
    if cuda.is_dir():
        onnxruntime.preload_dlls(cuda=True, cudnn=False, directory=str(cuda))
    if cudnn.is_dir():
        onnxruntime.preload_dlls(cuda=False, cudnn=True, msvc=False, directory=str(cudnn))


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        _preparar_cuda(Path(sys._MEIPASS))
    from image_studio.__main__ import principal

    sys.exit(principal(sys.argv[1:]))
