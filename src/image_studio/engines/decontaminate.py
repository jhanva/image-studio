"""Estimación del color real del frente en píxeles de borde (quita el halo del fondo)."""

from __future__ import annotations

import numpy as np
from pymatting import estimate_foreground_ml


def decontaminate(
    rgb: np.ndarray, alpha: np.ndarray, tile: int = 256, margen: int = 16
) -> np.ndarray:
    salida = rgb.copy()
    borde = (alpha > 0.01) & (alpha < 0.99)
    if not borde.any():
        return salida
    imagen = rgb.astype(np.float64) / 255.0
    alfa = alpha.astype(np.float64)
    alto, ancho = alpha.shape
    for y in range(0, alto, tile):
        for x in range(0, ancho, tile):
            nucleo = borde[y : y + tile, x : x + tile]
            if not nucleo.any():
                continue
            y0, x0 = max(0, y - margen), max(0, x - margen)
            y1, x1 = min(alto, y + tile + margen), min(ancho, x + tile + margen)
            frente = estimate_foreground_ml(imagen[y0:y1, x0:x1], alfa[y0:y1, x0:x1])
            alto_n, ancho_n = nucleo.shape
            bloque = frente[y - y0 : y - y0 + alto_n, x - x0 : x - x0 + ancho_n]
            bloque8 = np.clip(bloque * 255.0 + 0.5, 0, 255).astype(np.uint8)
            destino = salida[y : y + alto_n, x : x + ancho_n]
            destino[nucleo] = bloque8[nucleo]
    return salida
