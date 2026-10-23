"""Descarga, verificación y carga de modelos ONNX."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

Progreso = Callable[[int, int], None]
_BASE_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"


@dataclass(frozen=True)
class ModelSpec:
    nombre: str
    archivo: str
    url: str
    sha256: str
    tamano: int


MODELOS = {
    "birefnet": ModelSpec(
        "birefnet",
        "BiRefNet-general-epoch_244.onnx",
        _BASE_URL + "BiRefNet-general-epoch_244.onnx",
        "58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c",
        972666916,
    ),
    "birefnet_lite": ModelSpec(
        "birefnet_lite",
        "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
        _BASE_URL + "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
        "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333",
        224005088,
    ),
    "isnet": ModelSpec(
        "isnet",
        "isnet-general-use.onnx",
        _BASE_URL + "isnet-general-use.onnx",
        "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
        178648008,
    ),
}


class ModelError(Exception):
    """El modelo no se pudo descargar, verificar o cargar."""


def models_dir() -> Path:
    personalizado = os.environ.get("IMAGE_STUDIO_MODELS_DIR")
    if personalizado:
        return Path(personalizado)
    return Path(os.environ["LOCALAPPDATA"]) / "ImageStudio" / "models"


def ensure_model(spec: ModelSpec, progreso: Progreso | None = None) -> Path:
    """Devuelve la ruta local del modelo; lo descarga y verifica si falta."""
    destino = models_dir() / spec.archivo
    if destino.exists():
        if destino.stat().st_size == spec.tamano:
            return destino
        destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    try:
        _descargar(spec.url, parcial, spec.tamano, progreso)
        if _sha256(parcial) != spec.sha256:
            raise ModelError(f"Hash inválido para {spec.archivo}")
        parcial.replace(destino)
    except ModelError:
        parcial.unlink(missing_ok=True)
        raise
    except OSError as exc:
        parcial.unlink(missing_ok=True)
        raise ModelError(f"No se pudo descargar {spec.archivo}: {exc}") from exc
    return destino


def _descargar(url: str, destino: Path, tamano: int, progreso: Progreso | None) -> None:
    with urllib.request.urlopen(url, timeout=60) as respuesta, open(destino, "wb") as archivo:
        total = int(respuesta.headers.get("Content-Length") or tamano)
        leidos = 0
        while bloque := respuesta.read(1 << 20):
            archivo.write(bloque)
            leidos += len(bloque)
            if progreso:
                progreso(leidos, total)


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while bloque := archivo.read(1 << 20):
            resumen.update(bloque)
    return resumen.hexdigest()


@cache
def available_providers() -> list[str]:
    """CUDA primero si está disponible y sus DLL cargan; CPU siempre al final."""
    import onnxruntime as ort

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return ["CPUExecutionProvider"]
    try:
        ort.preload_dlls()
    except Exception:  # DLL de CUDA/cuDNN ausentes o incompatibles: se usa CPU
        return ["CPUExecutionProvider"]
    return ["CUDAExecutionProvider", "CPUExecutionProvider"]


def create_session(ruta: Path, dispositivo: str = "auto"):
    """Sesión ONNX Runtime; dispositivo es "auto" o "cpu"."""
    import onnxruntime as ort

    opciones = ort.SessionOptions()
    # Con el patrón de memoria, BiRefNet desborda 8 GB de VRAM y pasa de 1.5 s a 22 s.
    opciones.enable_mem_pattern = False
    opciones.log_severity_level = 3
    proveedores = ["CPUExecutionProvider"] if dispositivo == "cpu" else available_providers()
    try:
        return ort.InferenceSession(str(ruta), opciones, providers=proveedores)
    except Exception as exc:
        raise ModelError(f"No se pudo cargar {Path(ruta).name}: {exc}") from exc
