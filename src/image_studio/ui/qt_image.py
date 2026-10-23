"""Puentes entre arreglos numpy y QImage."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage

from image_studio.core.brush import Rect


def _alfa8(alpha: np.ndarray) -> np.ndarray:
    return np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)


class RgbaBuffer:
    """Arreglo RGBA que respalda un QImage sin copia: actualizar el arreglo actualiza la imagen."""

    def __init__(self, rgb: np.ndarray, alpha: np.ndarray):
        alto, ancho = alpha.shape
        self.datos = np.empty((alto, ancho, 4), np.uint8)
        self.datos[..., :3] = rgb
        self.datos[..., 3] = _alfa8(alpha)
        self.imagen = QImage(self.datos.data, ancho, alto, ancho * 4, QImage.Format.Format_RGBA8888)

    def update(self, rgb: np.ndarray, alpha: np.ndarray, rect: Rect) -> None:
        x0, y0, x1, y1 = rect
        self.datos[y0:y1, x0:x1, :3] = rgb[y0:y1, x0:x1]
        self.datos[y0:y1, x0:x1, 3] = _alfa8(alpha[y0:y1, x0:x1])


class RgbBuffer:
    """QImage opaco sobre un arreglo RGB, para la vista del original."""

    def __init__(self, rgb: np.ndarray):
        self.datos = np.ascontiguousarray(rgb)
        alto, ancho = self.datos.shape[:2]
        self.imagen = QImage(self.datos.data, ancho, alto, ancho * 3, QImage.Format.Format_RGB888)


def qimage_to_arrays(imagen: QImage) -> tuple[np.ndarray, np.ndarray | None]:
    """RGB uint8 y alfa float32 (None si es opaca) a partir de cualquier QImage."""
    rgba = imagen.convertToFormat(QImage.Format.Format_RGBA8888)
    alto, ancho = rgba.height(), rgba.width()
    crudo = np.frombuffer(rgba.constBits(), np.uint8, count=rgba.sizeInBytes())
    pixeles = crudo.reshape(alto, rgba.bytesPerLine())[:, : ancho * 4].reshape(alto, ancho, 4).copy()
    alfa = pixeles[..., 3]
    rgb = np.ascontiguousarray(pixeles[..., :3])
    if (alfa == 255).all():
        return rgb, None
    return rgb, alfa.astype(np.float32) / 255.0
