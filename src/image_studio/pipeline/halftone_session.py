"""Sesión de la herramienta de semitonos: imagen de impresión, borradores y caché por etapas.

El cálculo corre en otro hilo. Cada caché guarda la clave de lo que la produjo; un resultado solo se
guarda si su generación sigue siendo la actual, así que un cálculo viejo nunca contamina la caché.
"""

from __future__ import annotations

import math
import threading
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from image_studio.core.brush import Rect, brush_profile, footprint_rect, huella_en, stroke_points, union
from image_studio.core.export import ExportSettings, save
from image_studio.core.halftone.cleanup import CleanupResult, cleanup_mask
from image_studio.core.halftone.knockout import knockout_color
from image_studio.core.halftone.render import BORRAR, PROTEGER, compose_output, coverage_map, visible_alpha
from image_studio.core.halftone.screen import threshold_field
from image_studio.core.halftone.settings import DPI_IMPRESION, HalftoneSettings
from image_studio.core.history import MaskHistory
from image_studio.core.image_io import ImageDoc

MAX_PIXELES = 60_000_000
ANCHO_MIN_PULGADAS = 1.0
ANCHO_MAX_PULGADAS = 30.0

_LIMPIEZA = ("quitar_fondo", "fondo_interior", "colores_borrar", "tolerancia", "encoger_px")
_COBERTURA = ("knockout", "color_elegido", "alcance", "peso", "descartar", "bordes_limpios_px")
_TRAMA = ("lpi", "angulo", "ajustar_rejilla", "patron")


class ModoBorrador(str, Enum):
    BORRAR = "borrar"
    PROTEGER = "proteger"
    QUITAR = "quitar"


_VALOR = {ModoBorrador.BORRAR: BORRAR, ModoBorrador.PROTEGER: PROTEGER, ModoBorrador.QUITAR: 0}


@dataclass
class Borrador:
    modo: ModoBorrador = ModoBorrador.PROTEGER
    radio: float = 45.0
    """En píxeles de impresión."""


def _clave(ajustes: HalftoneSettings, campos: tuple[str, ...]) -> tuple:
    return tuple(getattr(ajustes, c) for c in campos)


class HalftoneSession:
    def __init__(self, doc: ImageDoc, ajustes: HalftoneSettings | None = None):
        self.doc = doc
        self.ajustes = ajustes or HalftoneSettings()
        self.borrador = Borrador()
        self.contadores: Counter[str] = Counter()
        self.generacion = 0
        self.ultimo_fondo = None
        self._lock = threading.Lock()
        self._version_imagen = 0
        self._version_marcas = 0
        self._caches: dict[str, tuple[tuple, object]] = {}
        self._ultimo: tuple[float, float] | None = None
        self._huella: np.ndarray | None = None
        self._alpha_origen = (
            doc.alpha.astype(np.float32) if doc.alpha is not None
            else np.ones(doc.rgb.shape[:2], np.float32)
        )
        self.ancho_pulgadas = 0.0
        self.rgb = doc.rgb
        self.alpha = self._alpha_origen
        self.marcas = np.zeros(self.alpha.shape, np.uint8)
        self.history = MaskHistory(self.marcas)
        self.set_ancho(doc.size[0] / DPI_IMPRESION)

    # --- tamaño de impresión ---

    @property
    def forma(self) -> tuple[int, int]:
        return self.alpha.shape

    @property
    def rect_completo(self) -> Rect:
        alto, ancho = self.forma
        return 0, 0, ancho, alto

    def ancho_maximo(self) -> float:
        ancho, alto = self.doc.size
        por_pixeles = math.sqrt(MAX_PIXELES * ancho / alto) / DPI_IMPRESION
        return min(ANCHO_MAX_PULGADAS, math.floor(por_pixeles * 100) / 100)

    def set_ancho(self, pulgadas: float) -> bool:
        """Remuestrea a la resolución de impresión. Devuelve True si hubo que limitar el ancho."""
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
        limite = self.ancho_maximo()
        limitado = pulgadas > limite
        pulgadas = min(max(pulgadas, ANCHO_MIN_PULGADAS), limite)
        ancho_src, alto_src = self.doc.size
        ancho = max(1, round(pulgadas * DPI_IMPRESION))
        alto = max(1, round(ancho * alto_src / ancho_src))
        if (alto, ancho) != self.forma or self.ancho_pulgadas == 0.0:
            if (ancho, alto) == (ancho_src, alto_src):
                self.rgb, self.alpha = self.doc.rgb, self._alpha_origen
            else:
                self.rgb = cv2.resize(self.doc.rgb, (ancho, alto), interpolation=cv2.INTER_LANCZOS4)
                alfa = cv2.resize(self._alpha_origen, (ancho, alto), interpolation=cv2.INTER_LANCZOS4)
                self.alpha = np.clip(alfa, 0.0, 1.0)
            if self.marcas.shape != (alto, ancho):
                self.marcas = cv2.resize(self.marcas, (ancho, alto), interpolation=cv2.INTER_NEAREST)
                self.history = MaskHistory(self.marcas)
            self._version_imagen += 1
            self._version_marcas += 1
            self.contadores["imagen"] += 1
            self.nueva_generacion()
        self.ancho_pulgadas = pulgadas
        return limitado

    # --- ajustes y generación ---

    def set_ajustes(self, ajustes: HalftoneSettings) -> int:
        self.ajustes = ajustes
        return self.nueva_generacion()

    def nueva_generacion(self) -> int:
        with self._lock:
            self.generacion += 1
            return self.generacion

    def _vigente(self, generacion: int | None) -> bool:
        return generacion is None or generacion == self.generacion

    def _cache(self, nombre: str, clave: tuple, calcular, generacion: int | None):
        guardado = self._caches.get(nombre)
        if guardado is not None and guardado[0] == clave:
            return guardado[1]
        valor = calcular()
        self.contadores[nombre] += 1
        with self._lock:
            if self._vigente(generacion):
                self._caches[nombre] = (clave, valor)
        return valor

    # --- cálculo ---

    def render(self, rect: Rect | None = None, generacion: int | None = None):
        """Devuelve (rect, RGBA) o None si la generación quedó vieja durante el cálculo."""
        ajustes, rgb, alpha, marcas = self.ajustes, self.rgb, self.alpha, self.marcas
        v_img, v_marcas = self._version_imagen, self._version_marcas
        alto, ancho = alpha.shape
        if rect is None:
            rect = (0, 0, ancho, alto)
        x0, y0, x1, y1 = max(0, rect[0]), max(0, rect[1]), min(ancho, rect[2]), min(alto, rect[3])
        if x0 >= x1 or y0 >= y1:
            return None
        rect = (x0, y0, x1, y1)

        clave_limpieza = (v_img, _clave(ajustes, _LIMPIEZA))
        limpieza: CleanupResult = self._cache(
            "limpieza", clave_limpieza, lambda: cleanup_mask(rgb, alpha, ajustes), generacion
        )
        self.ultimo_fondo = limpieza.fondo
        clave_visible = (clave_limpieza, v_marcas, ajustes.semitransparencia)
        visible = self._cache(
            "visible",
            clave_visible,
            lambda: visible_alpha(alpha, limpieza.eliminado, marcas, ajustes.semitransparencia),
            generacion,
        )
        if not self._vigente(generacion):
            return None
        k = knockout_color(ajustes, rgb, alpha)
        clave_cov = (clave_visible, _clave(ajustes, _COBERTURA), k)
        completo = rect == (0, 0, ancho, alto)
        guardada = self._caches.get("cobertura")
        zona = (slice(y0, y1), slice(x0, x1))
        if completo or (guardada is not None and guardada[0] == clave_cov):
            cov = self._cache(
                "cobertura", clave_cov, lambda: coverage_map(rgb, visible, marcas, ajustes, k), generacion
            )[zona]
        else:
            # Vista parcial sin caché: la cobertura solo depende de vecinos a bordes_limpios px.
            m = ajustes.bordes_limpios_px + 1
            ex0, ey0, ex1, ey1 = max(0, x0 - m), max(0, y0 - m), min(ancho, x1 + m), min(alto, y1 + m)
            amplia = (slice(ey0, ey1), slice(ex0, ex1))
            cov = coverage_map(rgb[amplia], visible[amplia], marcas[amplia], ajustes, k)
            cov = cov[y0 - ey0 : y1 - ey0, x0 - ex0 : x1 - ex0]
            self.contadores["cobertura_parcial"] += 1
        if not self._vigente(generacion):
            return None
        clave_umbral = (v_img, _clave(ajustes, _TRAMA))
        if completo:
            umbral = self._cache(
                "umbral", clave_umbral, lambda: threshold_field(rect, ajustes), generacion
            )
        else:
            umbral = threshold_field(rect, ajustes)
            self.contadores["umbral_parcial"] += 1
        salida = compose_output(rgb[zona], cov, umbral, k, ajustes.restaurar / 100.0)
        self.contadores["salida"] += 1
        if not self._vigente(generacion):
            return None
        return rect, salida

    def export(self, ruta: str | Path) -> Path:
        _, salida = self.render()
        return save(salida, ruta, ExportSettings(formato="png", dpi=DPI_IMPRESION))

    @staticmethod
    def hay_tinta(salida: np.ndarray) -> bool:
        return bool(salida[..., 3].any())

    # --- borradores ---

    @property
    def trazo_abierto(self) -> bool:
        return self._ultimo is not None

    def begin_stroke(self, x: float, y: float) -> Rect | None:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
        self.history.begin()
        self._huella = brush_profile(self.borrador.radio, 1.0) > 0.5
        self._ultimo = (x, y)
        return self._aplicar(x, y)

    def move_stroke(self, x: float, y: float) -> Rect | None:
        if self._ultimo is None:
            return None
        rect = None
        for px, py in stroke_points(self._ultimo, (x, y), paso=max(1.0, self.borrador.radio / 4)):
            rect = union(rect, self._aplicar(px, py))
        self._ultimo = (x, y)
        return rect

    def end_stroke(self) -> None:
        if self._ultimo is None:
            return
        self._ultimo = None
        self._huella = None
        self.history.end()
        self._marcas_cambiaron()

    def clear_marks(self) -> None:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
        if not self.marcas.any():
            return
        self.history.begin()
        self.history.touch(*self.rect_completo)
        self.marcas[...] = 0
        self.history.end()
        self._marcas_cambiaron()

    def undo(self) -> list[Rect]:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
        rects = self.history.undo()
        self._marcas_cambiaron()
        return rects

    def redo(self) -> list[Rect]:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
        rects = self.history.redo()
        self._marcas_cambiaron()
        return rects

    def _marcas_cambiaron(self) -> None:
        self._version_marcas += 1
        self.nueva_generacion()

    def _aplicar(self, x: float, y: float) -> Rect | None:
        rect = footprint_rect(x, y, self._huella, self.forma)
        if rect is None:
            return None
        self.history.touch(*rect)
        x0, y0, x1, y1 = rect
        zona = self.marcas[y0:y1, x0:x1]
        zona[huella_en(x, y, self._huella, rect)] = _VALOR[self.borrador.modo]
        self._version_marcas += 1
        return rect
