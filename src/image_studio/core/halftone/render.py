"""Etapas del semitono sobre arrays numpy (spec-semitonos 3.1 y 3.6).

E2 `visible_alpha`, E3 `coverage_map`, E4 `screen.threshold_field` y E5 `compose_output`.
E3 se calcula sobre la imagen completa (bordes limpios mira a los vecinos); E4 y E5 aceptan
cualquier recorte de las matrices completas.
"""

from __future__ import annotations

import cv2
import numpy as np

from image_studio.core.halftone.knockout import clean_edges, coverage, drop_small, restore_ink
from image_studio.core.halftone.screen import UMBRAL_MAX, threshold_field
from image_studio.core.halftone.settings import AlphaMode, Color, HalftoneSettings

BORRAR = 1
PROTEGER = 2


def visible_alpha(
    alpha: np.ndarray, eliminado: np.ndarray, marcas: np.ndarray, modo: AlphaMode
) -> np.ndarray:
    """Alfa float32 tras limpieza, borrador Borrar y modo de semitransparencia."""
    if modo is AlphaMode.CORTAR:
        visible = (alpha >= 0.5).astype(np.float32)
    else:
        visible = alpha.astype(np.float32, copy=True)
    visible[eliminado | (marcas == BORRAR)] = 0.0
    return visible


def coverage_map(
    rgb: np.ndarray, visible: np.ndarray, marcas: np.ndarray, ajustes: HalftoneSettings, k: Color
) -> np.ndarray:
    cov = coverage(rgb, k, ajustes.alcance / 100.0, ajustes.gamma)
    cov *= visible
    drop_small(cov, ajustes.descartar / 100.0)
    hay = visible > 0
    clean_edges(cov, hay, ajustes.bordes_limpios_px)
    cov[(marcas == PROTEGER) & hay] = 1.0
    return cov


def ink_mask(cov: np.ndarray, umbral: np.ndarray) -> np.ndarray:
    """Cobertura 1 siempre lleva tinta y cobertura 0 nunca."""
    return (cov >= 1.0) | (cov * UMBRAL_MAX > umbral)


def compose_output(
    rgb: np.ndarray, cov: np.ndarray, umbral: np.ndarray, k: Color, restaurar: float
) -> np.ndarray:
    """RGBA uint8 con alfa binario; RGB 0 donde no hay tinta."""
    tinta = ink_mask(cov, umbral)
    mascara = tinta.view(np.uint8)
    color = restore_ink(rgb, cov, k, restaurar) if restaurar > 0 else rgb
    salida = cv2.merge([*cv2.split(color), mascara * np.uint8(255)])
    # Sin tinta, todo el píxel queda en 0 (RGB incluido).
    return cv2.bitwise_and(salida, salida, mask=mascara)


def render(
    rgb: np.ndarray,
    alpha: np.ndarray,
    eliminado: np.ndarray,
    marcas: np.ndarray,
    ajustes: HalftoneSettings,
    k: Color,
) -> np.ndarray:
    """Las cuatro etapas sobre la imagen completa."""
    alto, ancho = alpha.shape
    visible = visible_alpha(alpha, eliminado, marcas, ajustes.semitransparencia)
    cov = coverage_map(rgb, visible, marcas, ajustes, k)
    umbral = threshold_field((0, 0, ancho, alto), ajustes)
    return compose_output(rgb, cov, umbral, k, ajustes.restaurar / 100.0)
