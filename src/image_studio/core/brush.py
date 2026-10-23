"""Pinceles sobre la máscara: Conservar sube el alfa, Borrar lo baja, Refinar marca zonas."""

from __future__ import annotations

from enum import Enum

import numpy as np

Rect = tuple[int, int, int, int]


class Modo(str, Enum):
    CONSERVAR = "conservar"
    BORRAR = "borrar"
    REFINAR = "refinar"


def brush_profile(radio: float, dureza: float) -> np.ndarray:
    """Huella cuadrada float32: 1 hasta radio*dureza y caída lineal hasta 0 en el radio."""
    if radio < 0.5:
        raise ValueError("radio debe ser >= 0.5")
    if not 0.0 <= dureza <= 1.0:
        raise ValueError("dureza debe estar entre 0 y 1")
    r = int(np.ceil(radio))
    filas, columnas = np.mgrid[-r : r + 1, -r : r + 1]
    distancia = np.hypot(filas, columnas)
    nucleo = radio * dureza
    if radio - nucleo < 1e-6:
        return (distancia <= radio).astype(np.float32)
    return np.clip((radio - distancia) / (radio - nucleo), 0.0, 1.0).astype(np.float32)


def footprint_rect(cx: float, cy: float, huella: np.ndarray, forma: tuple[int, int]) -> Rect | None:
    """Rectángulo (x0, y0, x1, y1) que cubre la huella centrada en (cx, cy), recortado a la imagen."""
    r = huella.shape[0] // 2
    alto, ancho = forma
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    x1, y1 = x0 + huella.shape[1], y0 + huella.shape[0]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(ancho, x1), min(alto, y1)
    if x0 >= x1 or y0 >= y1:
        return None
    return x0, y0, x1, y1


def huella_en(cx: float, cy: float, huella: np.ndarray, rect: Rect) -> np.ndarray:
    """Parte de la huella que cae dentro de rect (obtenido con footprint_rect)."""
    r = huella.shape[0] // 2
    ox, oy = int(round(cx)) - r, int(round(cy)) - r
    x0, y0, x1, y1 = rect
    return huella[y0 - oy : y1 - oy, x0 - ox : x1 - ox]


def stamp(mascara: np.ndarray, cx: float, cy: float, huella: np.ndarray, modo: Modo) -> Rect | None:
    rect = footprint_rect(cx, cy, huella, mascara.shape)
    if rect is None:
        return None
    x0, y0, x1, y1 = rect
    zona = mascara[y0:y1, x0:x1]
    parte = huella_en(cx, cy, huella, rect)
    if modo is Modo.CONSERVAR:
        np.maximum(zona, parte, out=zona)
    elif modo is Modo.BORRAR:
        np.minimum(zona, 1.0 - parte, out=zona)
    else:
        raise ValueError("stamp solo pinta con Conservar o Borrar")
    return rect


def stroke_points(
    desde: tuple[float, float], hasta: tuple[float, float], paso: float
) -> list[tuple[float, float]]:
    """Puntos entre dos posiciones separados como máximo por paso px; no incluye desde."""
    (xa, ya), (xb, yb) = desde, hasta
    n = max(1, int(np.ceil(float(np.hypot(xb - xa, yb - ya)) / max(paso, 1e-6))))
    return [(xa + (xb - xa) * i / n, ya + (yb - ya) * i / n) for i in range(1, n + 1)]


def union(a: Rect | None, b: Rect | None) -> Rect | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])
