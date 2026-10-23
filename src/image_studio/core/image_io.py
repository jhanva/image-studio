"""Carga de imágenes normalizadas a RGB de 8 bits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()

FORMATOS_ENTRADA = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)
_MODOS_16_BITS = ("I;16", "I;16B", "I;16L", "I")


class ImageLoadError(Exception):
    """La imagen no se pudo leer o su formato no está soportado."""


@dataclass
class ImageDoc:
    path: Path
    rgb: np.ndarray
    """HxWx3 uint8."""
    alpha: np.ndarray | None
    """HxW float32 en [0, 1] si el archivo traía transparencia."""
    dpi: tuple[float, float] | None
    icc_profile: bytes | None

    @property
    def size(self) -> tuple[int, int]:
        alto, ancho = self.rgb.shape[:2]
        return ancho, alto


def load_image(path: str | Path) -> ImageDoc:
    path = Path(path)
    if path.suffix.lower() not in FORMATOS_ENTRADA:
        raise ImageLoadError(f"Formato no soportado: {path.suffix or '(sin extensión)'}")
    try:
        with Image.open(path) as imagen:
            imagen.load()
            info = dict(imagen.info)
            orientada = ImageOps.exif_transpose(imagen)
            rgb, alpha = _a_rgb8(orientada)
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ImageLoadError(f"No se pudo leer {path.name}: {exc}") from exc
    return ImageDoc(
        path=path,
        rgb=rgb,
        alpha=alpha,
        dpi=_dpi(info.get("dpi")),
        icc_profile=info.get("icc_profile"),
    )


def _a_rgb8(imagen: Image.Image) -> tuple[np.ndarray, np.ndarray | None]:
    if imagen.mode in _MODOS_16_BITS:
        valores = np.array(imagen, dtype=np.float64)
        gris = np.clip(valores / 257.0 + 0.5, 0, 255).astype(np.uint8)
        return np.repeat(gris[..., None], 3, axis=2), None
    tiene_alfa = imagen.mode in ("RGBA", "LA", "PA") or (
        imagen.mode == "P" and "transparency" in imagen.info
    )
    if tiene_alfa:
        rgba = np.array(imagen.convert("RGBA"))
        return np.ascontiguousarray(rgba[..., :3]), rgba[..., 3].astype(np.float32) / 255.0
    return np.array(imagen.convert("RGB")), None


def _dpi(valor) -> tuple[float, float] | None:
    if not valor:
        return None
    return float(valor[0]), float(valor[1])
