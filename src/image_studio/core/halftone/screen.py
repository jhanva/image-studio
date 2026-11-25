"""Trama por umbral: funciones de punto, tablas de área y campo de umbral (spec-semitonos 3.2)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np

from image_studio.core.halftone.settings import DPI_IMPRESION, HalftoneSettings, Pattern

UMBRAL_MAX = 65535
_NIVELES = 1 << 16
_MUESTRAS = 512
_ONDA = 0.15
_ONDULADOS = (Pattern.LINEAS_ONDULADAS, Pattern.PUNTOS_ONDULADOS)
Rect = tuple[int, int, int, int]


def periodo_celdas(patron: Pattern) -> int:
    """Celdas que abarca un periodo del patrón en la dirección u."""
    return 4 if patron in _ONDULADOS else 1


def _centrada(t: np.ndarray) -> np.ndarray:
    return t - np.floor(t) - 0.5


def spot(patron: Pattern, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Valor de punto: mayor valor se entinta antes."""
    fu = _centrada(u)
    if patron in _ONDULADOS:
        fw = _centrada(v - _ONDA * np.sin(2 * np.pi * u / 4))
        if patron is Pattern.LINEAS_ONDULADAS:
            return -np.abs(fw)
        return np.cos(2 * np.pi * fu) + np.cos(2 * np.pi * fw)
    fv = _centrada(v)
    if patron is Pattern.REDONDO:
        return np.cos(2 * np.pi * fu) + np.cos(2 * np.pi * fv)
    if patron is Pattern.DIAMANTE:
        return -(np.abs(fu) + np.abs(fv))
    if patron is Pattern.ELIPSE:
        return -(fu * fu + (1.6 * fv) ** 2)
    if patron is Pattern.CUADRADO:
        return -np.maximum(np.abs(fu), np.abs(fv))
    if patron is Pattern.LINEA:
        return -np.abs(fv)
    raise ValueError(f"Patrón desconocido: {patron}")


@dataclass(frozen=True)
class AreaTable:
    """Convierte un valor de punto en la fracción del periodo con valor mayor (0 a UMBRAL_MAX)."""

    minimo: float
    maximo: float
    umbral: np.ndarray  # uint16, _NIVELES entradas

    def __call__(self, s: np.ndarray) -> np.ndarray:
        escala = (_NIVELES - 1) / (self.maximo - self.minimo)
        idx = ((s - self.minimo) * escala).astype(np.int32)
        np.clip(idx, 0, _NIVELES - 1, out=idx)
        return self.umbral[idx]


@cache
def area_table(patron: Pattern) -> AreaTable:
    k = periodo_celdas(patron)
    paso = (np.arange(_MUESTRAS) + 0.5) / _MUESTRAS
    u = (np.arange(_MUESTRAS * k) + 0.5) / _MUESTRAS
    valores = spot(patron, u[None, :], paso[:, None]).ravel().astype(np.float64)
    minimo, maximo = float(valores.min()), float(valores.max())
    if maximo - minimo < 1e-12:
        raise ValueError(f"Patrón constante: {patron}")
    # Histograma fino del valor de punto; el umbral de un nivel es el área estrictamente mayor.
    escala = (_NIVELES - 1) / (maximo - minimo)
    idx = np.clip(((valores - minimo) * escala).astype(np.int64), 0, _NIVELES - 1)
    cuenta = np.bincount(idx, minlength=_NIVELES).astype(np.float64)
    mayores = cuenta[::-1].cumsum()[::-1] - cuenta  # muestras en niveles superiores
    # Dentro del propio nivel se reparte la mitad, para no sesgar los niveles con muchas muestras.
    fraccion = (mayores + cuenta / 2) / valores.size
    umbral = np.round(fraccion * UMBRAL_MAX).astype(np.uint16)
    return AreaTable(minimo, maximo, umbral)


@dataclass(frozen=True)
class Screen:
    """Vector de celda en píxeles; si es entero, la trama es periódica sobre la rejilla."""

    bx: float
    by: float
    entero: bool

    @property
    def celda(self) -> float:
        return math.hypot(self.bx, self.by)

    @property
    def lpi(self) -> float:
        return DPI_IMPRESION / self.celda

    @property
    def angulo(self) -> float:
        return math.degrees(math.atan2(self.by, self.bx)) % 180.0


def _dif_angular(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def snap_screen(celda: float, angulo: float) -> Screen:
    """Vector entero más cercano en ángulo con largo a menos del 7% de la celda."""
    mejor = None
    radio = int(math.ceil(celda * 1.07)) + 1
    for by in range(0, radio + 1):
        for bx in range(-radio, radio + 1):
            if bx == 0 and by == 0:
                continue
            largo = math.hypot(bx, by)
            if abs(largo - celda) / celda > 0.07:
                continue
            clave = (_dif_angular(math.degrees(math.atan2(by, bx)), angulo), abs(largo - celda))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, bx, by)
    if mejor is None:
        rad = math.radians(angulo)
        bx, by = round(celda * math.cos(rad)), round(celda * math.sin(rad))
        if bx == 0 and by == 0:
            bx = 1
        return Screen(float(bx), float(by), True)
    return Screen(float(mejor[1]), float(mejor[2]), True)


def screen_for(ajustes: HalftoneSettings) -> Screen:
    celda = DPI_IMPRESION / ajustes.lpi
    if ajustes.ajustar_rejilla:
        return snap_screen(celda, ajustes.angulo)
    rad = math.radians(ajustes.angulo)
    return Screen(celda * math.cos(rad), celda * math.sin(rad), False)


def _campo(pantalla: Screen, patron: Pattern, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    l2 = pantalla.bx**2 + pantalla.by**2
    x = (xs.astype(np.float64) + 0.5)[None, :]
    y = (ys.astype(np.float64) + 0.5)[:, None]
    u = (x * pantalla.bx + y * pantalla.by) / l2
    v = (y * pantalla.bx - x * pantalla.by) / l2
    return area_table(patron)(spot(patron, u, v))


def periodo_px(pantalla: Screen, patron: Pattern) -> int | None:
    """Periodo en píxeles en x y en y si el vector es entero."""
    if not pantalla.entero:
        return None
    bx, by = int(pantalla.bx), int(pantalla.by)
    return periodo_celdas(patron) * (bx * bx + by * by) // math.gcd(bx, by)


@cache
def _baldosa(pantalla: Screen, patron: Pattern) -> np.ndarray:
    """Umbral por rango sobre los píxeles reales del periodo.

    Con celdas de pocos píxeles la tabla de área continua se desvía: los centros de píxel solo
    caen en unas decenas de posiciones de la celda. Ordenar los píxeles de la baldosa da una
    cobertura exacta hasta 1 / (píxeles por celda).
    """
    p = periodo_px(pantalla, patron)
    bx, by = int(pantalla.bx), int(pantalla.by)
    l2 = bx * bx + by * by
    x2 = (2 * np.arange(p, dtype=np.int64) + 1)[None, :]
    y2 = (2 * np.arange(p, dtype=np.int64) + 1)[:, None]
    # Posición exacta dentro del periodo, en enteros: 2*l2*u y 2*l2*v módulo el periodo.
    ku = (x2 * bx + y2 * by) % (2 * l2 * periodo_celdas(patron))
    kv = (y2 * bx - x2 * by) % (2 * l2)
    clave = (ku * (2 * l2) + kv).ravel()
    clases, primera, inversa = np.unique(clave, return_index=True, return_inverse=True)
    u = ku.ravel()[primera] / (2 * l2)
    v = kv.ravel()[primera] / (2 * l2)
    valores = spot(patron, u, v)
    # Redondear agrupa los valores iguales salvo error numérico; el orden estable resuelve empates.
    orden = np.argsort(-np.round(valores, 9), kind="stable")
    umbral = np.empty(clases.size, np.uint16)
    umbral[orden] = np.round((np.arange(clases.size) + 0.5) * UMBRAL_MAX / clases.size)
    return umbral[inversa].reshape(p, p)


def threshold_field(rect: Rect, ajustes: HalftoneSettings) -> np.ndarray:
    """Umbral uint16 del rectángulo (x0, y0, x1, y1) en coordenadas de la imagen."""
    x0, y0, x1, y1 = rect
    pantalla = screen_for(ajustes)
    p = periodo_px(pantalla, ajustes.patron)
    if p is None or p > 4096:
        return _campo(pantalla, ajustes.patron, np.arange(x0, x1), np.arange(y0, y1))
    baldosa = _baldosa(pantalla, ajustes.patron)
    filas = baldosa[np.arange(y0, y1) % p]
    reps = -(-(x1 - x0 + x0 % p) // p)
    return np.tile(filas, (1, reps))[:, x0 % p : x0 % p + (x1 - x0)]
