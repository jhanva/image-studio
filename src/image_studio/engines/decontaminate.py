"""Estimación del color real del frente en píxeles de borde (quita el halo del fondo)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numba
import numpy as np
from pymatting import estimate_foreground_ml

# estimate_foreground_ml usa funciones paralelas de numba; llamarlas desde varios hilos con la
# capa workqueue termina el proceso. "threadsafe" exige omp o tbb, o falla con un error claro.
numba.config.THREADING_LAYER = "threadsafe"


def decontaminate(
    rgb: np.ndarray,
    alpha: np.ndarray,
    tile: int = 256,
    margen: int = 16,
    hilos: int | None = None,
) -> np.ndarray:
    salida = rgb.copy()
    borde = (alpha > 0.01) & (alpha < 0.99)
    if not borde.any():
        return salida
    imagen = rgb.astype(np.float64) / 255.0
    alfa = alpha.astype(np.float64)
    alto, ancho = alpha.shape
    bloques = [
        (y, x)
        for y in range(0, alto, tile)
        for x in range(0, ancho, tile)
        if borde[y : y + tile, x : x + tile].any()
    ]

    def estimar(bloque: tuple[int, int]) -> np.ndarray:
        y, x = bloque
        y0, x0 = max(0, y - margen), max(0, x - margen)
        y1, x1 = min(alto, y + tile + margen), min(ancho, x + tile + margen)
        frente = estimate_foreground_ml(imagen[y0:y1, x0:x1], alfa[y0:y1, x0:x1])
        return frente[y - y0 : y - y0 + tile, x - x0 : x - x0 + tile]

    with ThreadPoolExecutor(hilos or os.cpu_count() or 1) as pool:
        for (y, x), frente in zip(bloques, pool.map(estimar, bloques)):
            nucleo = borde[y : y + tile, x : x + tile]
            alto_n, ancho_n = nucleo.shape
            bloque8 = np.clip(frente[:alto_n, :ancho_n] * 255.0 + 0.5, 0, 255).astype(np.uint8)
            destino = salida[y : y + alto_n, x : x + ancho_n]
            destino[nucleo] = bloque8[nucleo]
    return salida
