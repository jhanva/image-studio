"""Operaciones sobre máscaras alfa float32 en [0, 1]."""

from __future__ import annotations

import cv2
import numpy as np

FONDO, DESCONOCIDO, FRENTE = 0, 128, 255


def _nucleo(radio: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))


def make_trimap(alpha: np.ndarray, banda_px: int, umbral: float = 0.5) -> np.ndarray:
    """Frente y fondo seguros, con una banda desconocida de banda_px a cada lado del borde."""
    if banda_px < 1:
        raise ValueError("banda_px debe ser >= 1")
    binaria = (alpha >= umbral).astype(np.uint8)
    nucleo = _nucleo(banda_px)
    trimap = np.full(alpha.shape, DESCONOCIDO, np.uint8)
    trimap[cv2.erode(binaria, nucleo) == 1] = FRENTE
    trimap[cv2.dilate(binaria, nucleo) == 0] = FONDO
    trimap[(alpha > 0.05) & (alpha < 0.95)] = DESCONOCIDO
    return trimap


def adjust_edge(
    alpha: np.ndarray, desplazamiento_px: int = 0, suavizado_px: float = 0.0
) -> np.ndarray:
    """Expande (positivo) o contrae (negativo) el borde y luego lo suaviza."""
    salida = alpha.astype(np.float32, copy=True)
    if desplazamiento_px > 0:
        salida = cv2.dilate(salida, _nucleo(desplazamiento_px))
    elif desplazamiento_px < 0:
        salida = cv2.erode(salida, _nucleo(-desplazamiento_px))
    if suavizado_px > 0:
        salida = cv2.GaussianBlur(salida, (0, 0), sigmaX=suavizado_px)
    return np.clip(salida, 0.0, 1.0)


def content_bbox(alpha: np.ndarray, umbral: float = 0.01) -> tuple[int, int, int, int] | None:
    """Caja (x0, y0, x1, y1) con x1 e y1 exclusivos, o None si la máscara está vacía."""
    filas, columnas = np.nonzero(alpha > umbral)
    if filas.size == 0:
        return None
    return int(columnas.min()), int(filas.min()), int(columnas.max()) + 1, int(filas.max()) + 1
