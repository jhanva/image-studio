"""Refinar borde: matting solo sobre los píxeles pintados con el pincel Refinar."""

from __future__ import annotations

import numpy as np

from image_studio.core.brush import Rect
from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE
from image_studio.engines.base import Matter


def region_bbox(pintado: np.ndarray, margen: int = 32) -> Rect | None:
    """Caja de lo pintado con margen, recortada a la imagen; el margen da frente y fondo conocidos."""
    filas, columnas = np.nonzero(pintado)
    if filas.size == 0:
        return None
    alto, ancho = pintado.shape
    return (
        max(0, int(columnas.min()) - margen),
        max(0, int(filas.min()) - margen),
        min(ancho, int(columnas.max()) + 1 + margen),
        min(alto, int(filas.max()) + 1 + margen),
    )


def refine_region(
    rgb: np.ndarray, alpha: np.ndarray, pintado: np.ndarray, matter: Matter, caja: Rect
) -> Rect:
    """Modifica alpha en el lugar, solo en los píxeles pintados de la caja."""
    x0, y0, x1, y1 = caja
    alfa = alpha[y0:y1, x0:x1]
    region = pintado[y0:y1, x0:x1]
    trimap = np.where(alfa >= 0.5, FRENTE, FONDO).astype(np.uint8)
    trimap[region] = DESCONOCIDO
    refinado = matter.refine(rgb[y0:y1, x0:x1], trimap, alfa)
    alfa[region] = refinado[region]
    return caja
