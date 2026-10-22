"""Matting clásico (closed-form de pymatting) por bloques sobre la banda desconocida."""

from __future__ import annotations

import numpy as np
from pymatting import estimate_alpha_cf

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE


class ClassicMatter:
    nombre = "clasico"

    def __init__(self, tile: int = 256, margen: int = 32):
        self.tile = tile
        self.margen = margen

    def refine(self, rgb: np.ndarray, trimap: np.ndarray, grueso: np.ndarray) -> np.ndarray:
        alfa = grueso.astype(np.float32, copy=True)
        alfa[trimap == FRENTE] = 1.0
        alfa[trimap == FONDO] = 0.0
        imagen = rgb.astype(np.float64) / 255.0
        trimap_01 = trimap.astype(np.float64) / 255.0
        alto, ancho = trimap.shape
        for y in range(0, alto, self.tile):
            for x in range(0, ancho, self.tile):
                nucleo = trimap[y : y + self.tile, x : x + self.tile]
                desconocido = nucleo == DESCONOCIDO
                if not desconocido.any():
                    continue
                y0, x0 = max(0, y - self.margen), max(0, x - self.margen)
                y1 = min(alto, y + self.tile + self.margen)
                x1 = min(ancho, x + self.tile + self.margen)
                recorte = trimap_01[y0:y1, x0:x1]
                # Sin frente y fondo seguros el sistema no tiene restricciones: se deja el grueso.
                if not ((recorte == 0.0).any() and (recorte == 1.0).any()):
                    continue
                estimado = estimate_alpha_cf(imagen[y0:y1, x0:x1], recorte)
                alto_n, ancho_n = nucleo.shape
                bloque = estimado[y - y0 : y - y0 + alto_n, x - x0 : x - x0 + ancho_n]
                destino = alfa[y : y + alto_n, x : x + ancho_n]
                destino[desconocido] = bloque[desconocido]
        return np.clip(alfa, 0.0, 1.0)
