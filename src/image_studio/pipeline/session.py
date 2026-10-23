"""Sesión de edición: máscara, historial, pinceles y exportación, sin dependencias de Qt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from image_studio.core.brush import (
    Modo,
    Rect,
    brush_profile,
    footprint_rect,
    huella_en,
    stamp,
    stroke_points,
    union,
)
from image_studio.core.export import ExportSettings, compose, save
from image_studio.core.history import MaskHistory
from image_studio.core.image_io import ImageDoc
from image_studio.engines.base import Matter
from image_studio.engines.decontaminate import decontaminate
from image_studio.pipeline.refine_region import refine_region, region_bbox
from image_studio.pipeline.remove_bg import RemovalResult


@dataclass
class Pincel:
    modo: Modo = Modo.CONSERVAR
    radio: float = 30.0
    dureza: float = 0.8


class EditSession:
    def __init__(self, doc: ImageDoc):
        self.doc = doc
        alto, ancho = doc.rgb.shape[:2]
        if doc.alpha is not None:
            self.alpha = doc.alpha.astype(np.float32, copy=True)
        else:
            self.alpha = np.ones((alto, ancho), np.float32)
        self.rgb = doc.rgb
        """Color que se muestra: el original o el limpiado por el último quitar fondo."""
        self.resultado: RemovalResult | None = None
        self.history = MaskHistory(self.alpha)
        self.pincel = Pincel()
        self.refinado_pendiente = False
        self._modo: Modo | None = None
        self._ultimo: tuple[float, float] | None = None
        self._huella: np.ndarray | None = None
        self._pintado: np.ndarray | None = None

    @property
    def rect_completo(self) -> Rect:
        alto, ancho = self.alpha.shape
        return 0, 0, ancho, alto

    @property
    def trazo_abierto(self) -> bool:
        return self._ultimo is not None or self.refinado_pendiente

    def apply_result(self, resultado: RemovalResult) -> Rect:
        self._exigir_sin_trazo()
        self.history.begin()
        self.history.touch(*self.rect_completo)
        self.alpha[...] = resultado.alpha
        self.history.end()
        self.rgb = resultado.rgb
        self.resultado = resultado
        return self.rect_completo

    def begin_stroke(self, x: float, y: float) -> Rect | None:
        self._exigir_sin_trazo()
        self.history.begin()
        self._modo = self.pincel.modo
        self._huella = brush_profile(self.pincel.radio, self.pincel.dureza)
        if self._modo is Modo.REFINAR:
            self._pintado = np.zeros(self.alpha.shape, bool)
        self._ultimo = (x, y)
        return self._aplicar(x, y)

    def move_stroke(self, x: float, y: float) -> Rect | None:
        if self._ultimo is None:
            return None
        rect = None
        for px, py in stroke_points(self._ultimo, (x, y), paso=max(1.0, self.pincel.radio / 4)):
            rect = union(rect, self._aplicar(px, py))
        self._ultimo = (x, y)
        return rect

    def end_stroke(self) -> None:
        if self._ultimo is None:
            return
        self._ultimo = None
        self._huella = None
        if self._modo is Modo.REFINAR:
            # El paso del historial sigue abierto hasta que el matting termina en otro hilo.
            self.refinado_pendiente = True
        else:
            self.history.end()

    def refine_pending(self, matter: Matter) -> Rect | None:
        if not self.refinado_pendiente:
            return None
        pintado, self._pintado = self._pintado, None
        caja = region_bbox(pintado)
        rect = None
        if caja is not None:
            self.history.touch(*caja)
            rect = refine_region(self.doc.rgb, self.alpha, pintado, matter, caja)
        self.history.end()
        self.refinado_pendiente = False
        return rect

    def cancel_refine(self) -> None:
        if not self.refinado_pendiente:
            return
        self._pintado = None
        self.history.end()
        self.refinado_pendiente = False

    def undo(self) -> list[Rect]:
        self._exigir_sin_trazo()
        return self.history.undo()

    def redo(self) -> list[Rect]:
        self._exigir_sin_trazo()
        return self.history.redo()

    def export(self, ruta: str | Path, ajustes: ExportSettings, limpiar_color: bool) -> Path:
        rgb = decontaminate(self.doc.rgb, self.alpha) if limpiar_color else self.doc.rgb
        return save(compose(rgb, self.alpha, ajustes), ruta, ajustes, self.doc.icc_profile)

    def _aplicar(self, x: float, y: float) -> Rect | None:
        rect = footprint_rect(x, y, self._huella, self.alpha.shape)
        if rect is None:
            return None
        if self._modo is Modo.REFINAR:
            x0, y0, x1, y1 = rect
            self._pintado[y0:y1, x0:x1] |= huella_en(x, y, self._huella, rect) > 0
            return rect
        self.history.touch(*rect)
        return stamp(self.alpha, x, y, self._huella, self._modo)

    def _exigir_sin_trazo(self) -> None:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
