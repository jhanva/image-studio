"""Composición del recorte con su fondo y escritura del archivo final."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image

from image_studio.core.mask_ops import content_bbox

FORMATOS_SALIDA = {"png": "PNG", "webp": "WEBP", "jpg": "JPEG"}
BLANCO = (255, 255, 255)


class Fondo(str, Enum):
    TRANSPARENTE = "transparente"
    BLANCO = "blanco"
    COLOR = "color"


@dataclass(frozen=True)
class ExportSettings:
    formato: str = "png"
    fondo: Fondo = Fondo.TRANSPARENTE
    color: tuple[int, int, int] = BLANCO
    recortar: bool = False
    margen_px: int = 0
    dpi: int | None = None

    def __post_init__(self) -> None:
        if self.formato not in FORMATOS_SALIDA:
            raise ValueError(f"Formato de salida no soportado: {self.formato}")
        if self.margen_px < 0:
            raise ValueError("margen_px debe ser >= 0")


def compose(rgb: np.ndarray, alpha: np.ndarray, ajustes: ExportSettings) -> np.ndarray:
    """Devuelve HxWx4 uint8 si el fondo es transparente, o HxWx3 uint8 con el fondo aplicado."""
    if ajustes.recortar:
        rgb, alpha = _recortar(rgb, alpha, ajustes.margen_px)
    fondo = ajustes.fondo
    if fondo is Fondo.TRANSPARENTE and ajustes.formato == "jpg":
        fondo = Fondo.BLANCO
    if fondo is Fondo.TRANSPARENTE:
        alfa8 = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return np.dstack([rgb, alfa8])
    color = np.array(BLANCO if fondo is Fondo.BLANCO else ajustes.color, np.float32)
    peso = alpha[..., None].astype(np.float32)
    mezcla = rgb.astype(np.float32) * peso + color * (1.0 - peso)
    return np.clip(mezcla + 0.5, 0, 255).astype(np.uint8)


def save(
    imagen: np.ndarray, path: str | Path, ajustes: ExportSettings, icc_profile: bytes | None = None
) -> Path:
    destino = Path(path).with_suffix("." + ajustes.formato)
    destino.parent.mkdir(parents=True, exist_ok=True)
    opciones: dict = {}
    if ajustes.dpi:
        opciones["dpi"] = (ajustes.dpi, ajustes.dpi)
    if icc_profile:
        opciones["icc_profile"] = icc_profile
    if ajustes.formato == "webp":
        opciones["lossless"] = True
    if ajustes.formato == "jpg":
        opciones.update(quality=95, subsampling=0)
    Image.fromarray(imagen).save(destino, FORMATOS_SALIDA[ajustes.formato], **opciones)
    return destino


def _recortar(rgb: np.ndarray, alpha: np.ndarray, margen: int):
    caja = content_bbox(alpha)
    if caja is None:
        return rgb, alpha
    alto, ancho = alpha.shape
    x0, y0, x1, y1 = caja
    x0, y0 = max(0, x0 - margen), max(0, y0 - margen)
    x1, y1 = min(ancho, x1 + margen), min(alto, y1 + margen)
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
