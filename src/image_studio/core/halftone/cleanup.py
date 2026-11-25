"""Limpieza previa al semitono: fondo sólido, colores borrados y encoger borde (spec-semitonos 3.3)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from image_studio.core.halftone.knockout import border_pixels
from image_studio.core.halftone.settings import Color, HalftoneSettings

_CRUZ = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))


@dataclass
class CleanupResult:
    eliminado: np.ndarray
    """HxW bool: píxeles que la limpieza deja sin tinta."""
    fondo: Color | None
    """Color de fondo detectado, o None si no se pidió o el marco no tiene píxeles opacos."""


def border_color(rgb: np.ndarray, alpha: np.ndarray) -> Color | None:
    """Color más frecuente entre los píxeles opacos del marco de 1 px."""
    pixeles = border_pixels(rgb, alpha).astype(np.int32)
    if pixeles.size == 0:
        return None
    claves = (pixeles[:, 0] << 16) | (pixeles[:, 1] << 8) | pixeles[:, 2]
    valores, cuentas = np.unique(claves, return_counts=True)
    clave = int(valores[np.argmax(cuentas)])
    return (clave >> 16) & 255, (clave >> 8) & 255, clave & 255


def similar(rgb: np.ndarray, color: Color, tolerancia: float) -> np.ndarray:
    """Diferencia por canal menor o igual a la tolerancia (en niveles 0-255)."""
    t = int(np.floor(tolerancia))
    bajo = np.array([max(0, c - t) for c in color], np.uint8)
    alto = np.array([min(255, c + t) for c in color], np.uint8)
    return cv2.inRange(rgb, bajo, alto).view(bool)


def _toca_el_borde(region: np.ndarray) -> np.ndarray:
    n, etiquetas = cv2.connectedComponents(region.view(np.uint8), connectivity=4)
    marco = np.concatenate([etiquetas[0], etiquetas[-1], etiquetas[:, 0], etiquetas[:, -1]])
    del_borde = np.zeros(n, bool)
    del_borde[marco] = True
    del_borde[0] = False
    return del_borde[etiquetas]


def cleanup_mask(rgb: np.ndarray, alpha: np.ndarray, ajustes: HalftoneSettings) -> CleanupResult:
    tol = ajustes.tolerancia * 255.0 / 100.0
    opaco = alpha > 0
    eliminado = np.zeros(alpha.shape, bool)
    fondo = None
    if ajustes.quitar_fondo:
        fondo = border_color(rgb, alpha)
        if fondo is not None:
            parecido = similar(rgb, fondo, tol) & opaco
            if ajustes.fondo_interior:
                eliminado |= parecido
            else:
                # Lo transparente también deja pasar la inundación desde el borde.
                eliminado |= _toca_el_borde(parecido | ~opaco) & parecido
    for color in ajustes.colores_borrar:
        eliminado |= similar(rgb, color, tol) & opaco
    if ajustes.encoger_px > 0:
        visible = (opaco & ~eliminado).astype(np.uint8)
        erosionado = cv2.erode(visible, _CRUZ, iterations=ajustes.encoger_px).astype(bool)
        eliminado |= visible.astype(bool) & ~erosionado
    return CleanupResult(eliminado, fondo)
