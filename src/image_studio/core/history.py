"""Historial deshacer/rehacer de la máscara guardando solo los tiles que cambia cada paso."""

from __future__ import annotations

from collections import deque

import numpy as np

Rect = tuple[int, int, int, int]
_Paso = dict[tuple[int, int], np.ndarray]


class MaskHistory:
    """La máscara se modifica en el lugar; antes de cambiar una zona se llama a touch()."""

    def __init__(
        self, mascara: np.ndarray, tile: int = 256, max_pasos: int = 50, max_bytes: int = 1 << 30
    ):
        self.mascara = mascara
        self.tile = tile
        self.max_pasos = max_pasos
        self.max_bytes = max_bytes
        self._deshacer: deque[_Paso] = deque()
        self._rehacer: list[_Paso] = []
        self._actual: _Paso | None = None

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._deshacer)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self._rehacer)

    @property
    def bytes_usados(self) -> int:
        pasos = list(self._deshacer) + self._rehacer
        return sum(tile.nbytes for paso in pasos for tile in paso.values())

    def begin(self) -> None:
        if self._actual is not None:
            raise RuntimeError("Ya hay un paso abierto")
        self._actual = {}

    def touch(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Guarda el estado previo de los tiles que cubren el rectángulo, una vez por paso."""
        if self._actual is None:
            raise RuntimeError("touch() sin begin()")
        alto, ancho = self.mascara.shape
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(ancho, x1), min(alto, y1)
        if x0 >= x1 or y0 >= y1:
            return
        t = self.tile
        for ty in range(y0 // t, (y1 - 1) // t + 1):
            for tx in range(x0 // t, (x1 - 1) // t + 1):
                if (ty, tx) not in self._actual:
                    self._actual[(ty, tx)] = self.mascara[ty * t : (ty + 1) * t, tx * t : (tx + 1) * t].copy()

    def end(self) -> None:
        if self._actual is None:
            raise RuntimeError("end() sin begin()")
        paso, self._actual = self._actual, None
        if not paso:
            return
        self._deshacer.append(paso)
        self._rehacer.clear()
        while len(self._deshacer) > self.max_pasos or (
            len(self._deshacer) > 1 and self.bytes_usados > self.max_bytes
        ):
            self._deshacer.popleft()

    def undo(self) -> list[Rect]:
        if not self._deshacer:
            return []
        paso = self._deshacer.pop()
        self._rehacer.append(paso)
        return self._intercambiar(paso)

    def redo(self) -> list[Rect]:
        if not self._rehacer:
            return []
        paso = self._rehacer.pop()
        self._deshacer.append(paso)
        return self._intercambiar(paso)

    def _intercambiar(self, paso: _Paso) -> list[Rect]:
        """Pone en la máscara lo guardado y guarda lo que había: el paso queda listo para el sentido contrario."""
        t = self.tile
        rects = []
        for (ty, tx), guardado in paso.items():
            zona = self.mascara[ty * t : (ty + 1) * t, tx * t : (tx + 1) * t]
            actual = zona.copy()
            zona[...] = guardado
            paso[(ty, tx)] = actual
            alto, ancho = zona.shape
            rects.append((tx * t, ty * t, tx * t + ancho, ty * t + alto))
        return rects
