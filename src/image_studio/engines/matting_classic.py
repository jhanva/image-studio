"""Matting clásico (closed-form de pymatting) por bloques sobre la banda desconocida."""

from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import dataclass

import numpy as np

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE

# pymatting compila con numba al importarse (unos 40 s la primera vez en un equipo nuevo);
# se carga en la primera llamada para no congelar el arranque de la app.
estimate_alpha_cf = None
ichol = None


def _cargar_pymatting() -> None:
    global estimate_alpha_cf, ichol
    if estimate_alpha_cf is None:
        from pymatting import estimate_alpha_cf as funcion

        estimate_alpha_cf = funcion
    if ichol is None:
        from pymatting.preconditioner.ichol import ichol as funcion

        ichol = funcion


# Elementos reservados por fila del sistema; un bloque de 320x320 usa menos de 30.
_ELEMENTOS_POR_FILA = 100


def _precondicionador(A):
    # pymatting reserva por defecto 250 millones de elementos (unos 4 GB) por bloque y los
    # mantiene vivos mientras dura el solver; con varios bloques agota la memoria en Windows.
    return ichol(A, max_nnz=max(1_000_000, _ELEMENTOS_POR_FILA * A.shape[0]))


@dataclass(frozen=True)
class _Bloque:
    y: int
    x: int
    y0: int
    x0: int
    y1: int
    x1: int
    desconocido: np.ndarray


class ClassicMatter:
    nombre = "clasico"

    def __init__(self, tile: int = 256, margen: int = 32, hilos: int | None = None):
        self.tile = tile
        self.margen = margen
        self.hilos = hilos or os.cpu_count() or 1

    def refine(self, rgb: np.ndarray, trimap: np.ndarray, grueso: np.ndarray) -> np.ndarray:
        _cargar_pymatting()
        alfa = grueso.astype(np.float32, copy=True)
        alfa[trimap == FRENTE] = 1.0
        alfa[trimap == FONDO] = 0.0
        imagen = rgb.astype(np.float64) / 255.0
        trimap_01 = trimap.astype(np.float64) / 255.0
        bloques = self._bloques(trimap, trimap_01)

        def estimar(b: _Bloque) -> np.ndarray:
            return estimate_alpha_cf(
                imagen[b.y0 : b.y1, b.x0 : b.x1],
                trimap_01[b.y0 : b.y1, b.x0 : b.x1],
                preconditioner=_precondicionador,
            )

        # Los núcleos de pymatting liberan el GIL, así que los bloques escalan con los hilos.
        # ichol imprime "PERFORMANCE WARNING" cada vez que reintenta con otro desplazamiento.
        with redirect_stdout(io.StringIO()), ThreadPoolExecutor(self.hilos) as pool:
            for b, estimado in zip(bloques, pool.map(estimar, bloques)):
                alto_n, ancho_n = b.desconocido.shape
                recorte = estimado[b.y - b.y0 : b.y - b.y0 + alto_n, b.x - b.x0 : b.x - b.x0 + ancho_n]
                destino = alfa[b.y : b.y + alto_n, b.x : b.x + ancho_n]
                destino[b.desconocido] = recorte[b.desconocido]
        return np.clip(alfa, 0.0, 1.0)

    def _bloques(self, trimap: np.ndarray, trimap_01: np.ndarray) -> list[_Bloque]:
        alto, ancho = trimap.shape
        bloques = []
        for y in range(0, alto, self.tile):
            for x in range(0, ancho, self.tile):
                desconocido = trimap[y : y + self.tile, x : x + self.tile] == DESCONOCIDO
                if not desconocido.any():
                    continue
                y0, x0 = max(0, y - self.margen), max(0, x - self.margen)
                y1 = min(alto, y + self.tile + self.margen)
                x1 = min(ancho, x + self.tile + self.margen)
                recorte = trimap_01[y0:y1, x0:x1]
                # Sin frente y fondo seguros el sistema no tiene restricciones: se deja el grueso.
                if not ((recorte == 0.0).any() and (recorte == 1.0).any()):
                    continue
                bloques.append(_Bloque(y, x, y0, x0, y1, x1, desconocido))
        return bloques
