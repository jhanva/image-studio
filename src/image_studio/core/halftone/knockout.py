"""Distancia al color de la camiseta, cobertura de tinta y reglas de impresión (spec-semitonos 3.1)."""

from __future__ import annotations

import cv2
import numpy as np

from image_studio.core.halftone.settings import Color, HalftoneSettings, KnockoutMode

NEGRO: Color = (0, 0, 0)
BLANCO: Color = (255, 255, 255)
_CRUZ = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))


def channel_distance(k: int) -> np.ndarray:
    """Distancia normalizada de cada valor 0-255 al valor k del canal, float32."""
    c = np.arange(256, dtype=np.float32)
    d = np.zeros(256, np.float32)
    if k < 255:
        arriba = c > k
        d[arriba] = (c[arriba] - k) / (255 - k)
    if k > 0:
        abajo = c < k
        d[abajo] = (k - c[abajo]) / k
    return d


def coverage_luts(k: Color, alcance: float, gamma: float) -> list[np.ndarray]:
    """Una tabla por canal. La cobertura es creciente en la distancia, así que
    cov(max(d_r, d_g, d_b)) = max(cov(d_r), cov(d_g), cov(d_b))."""
    return [np.minimum(1.0, channel_distance(kc) / alcance) ** gamma for kc in k]


def distance(rgb: np.ndarray, k: Color) -> np.ndarray:
    tablas = [channel_distance(kc) for kc in k]
    return np.maximum(np.maximum(tablas[0][rgb[..., 0]], tablas[1][rgb[..., 1]]), tablas[2][rgb[..., 2]])


def coverage(rgb: np.ndarray, k: Color, alcance: float, gamma: float) -> np.ndarray:
    """alcance en (0, 1]. Devuelve float32 HxW en [0, 1]."""
    r, g, b = coverage_luts(k, alcance, gamma)
    cov = r.astype(np.float32)[rgb[..., 0]]
    np.maximum(cov, g.astype(np.float32)[rgb[..., 1]], out=cov)
    np.maximum(cov, b.astype(np.float32)[rgb[..., 2]], out=cov)
    return cov


def drop_small(cov: np.ndarray, umbral: float) -> None:
    """En el lugar: bajo el umbral no hay tinta y sobre 1 - umbral la tinta es sólida."""
    if umbral <= 0:
        return
    cov[cov < umbral] = 0.0
    cov[cov > 1.0 - umbral] = 1.0


def clean_edges(cov: np.ndarray, visible: np.ndarray, n: int) -> None:
    """En el lugar: dilata n px la zona sólida, dentro de lo visible."""
    if n <= 0:
        return
    solido = (cov >= 1.0).astype(np.uint8)
    dilatado = cv2.dilate(solido, _CRUZ, iterations=n).astype(bool)
    cov[dilatado & visible] = 1.0


def restore_ink(rgb: np.ndarray, cov: np.ndarray, k: Color, fuerza: float) -> np.ndarray:
    """Deshace la mezcla tinta-camiseta en la proporción fuerza (0 a 1). Devuelve uint8."""
    if fuerza <= 0:
        return rgb
    parcial = (cov > 0) & (cov < 1)
    if not parcial.any():
        return rgb
    salida = rgb.copy()
    c = rgb[parcial].astype(np.float32)
    kk = np.asarray(k, np.float32)
    factor = 1.0 + (1.0 / cov[parcial] - 1.0) * fuerza
    salida[parcial] = np.clip(kk + (c - kk) * factor[:, None] + 0.5, 0, 255).astype(np.uint8)
    return salida


def border_pixels(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Píxeles opacos del marco de 1 px, Nx3."""
    alto, ancho = alpha.shape
    marco = np.zeros((alto, ancho), bool)
    marco[0, :] = marco[-1, :] = marco[:, 0] = marco[:, -1] = True
    return rgb[marco & (alpha > 0)]


def auto_knockout(rgb: np.ndarray, alpha: np.ndarray) -> Color:
    """Negro o blanco, el más cercano al color medio del marco."""
    pixeles = border_pixels(rgb, alpha)
    if pixeles.size == 0:
        return NEGRO
    return NEGRO if pixeles.mean() < 127.5 else BLANCO


def knockout_color(ajustes: HalftoneSettings, rgb: np.ndarray, alpha: np.ndarray) -> Color:
    modo = ajustes.knockout
    if modo is KnockoutMode.NEGRO:
        return NEGRO
    if modo is KnockoutMode.BLANCO:
        return BLANCO
    if modo is KnockoutMode.ELEGIDO:
        return ajustes.color_elegido
    return auto_knockout(rgb, alpha)
