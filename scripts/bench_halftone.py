"""Mide las etapas del semitono sobre una imagen sintética (spec-semitonos S1 y S2).

Uso: .\\.venv\\Scripts\\python.exe -X utf8 scripts\\bench_halftone.py [--ancho 3600 --alto 4800]
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from image_studio.core.halftone.cleanup import cleanup_mask
from image_studio.core.halftone.knockout import NEGRO
from image_studio.core.halftone.render import compose_output, coverage_map, visible_alpha
from image_studio.core.halftone.screen import threshold_field
from image_studio.core.halftone.settings import HalftoneSettings, Pattern


def _imagen(ancho: int, alto: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[:alto, :ancho].astype(np.float32)
    rgb = np.empty((alto, ancho, 3), np.uint8)
    rgb[..., 0] = (xx / ancho * 255).astype(np.uint8)
    rgb[..., 1] = (yy / alto * 255).astype(np.uint8)
    rgb[..., 2] = ((np.sin(xx / 97) * np.cos(yy / 53) + 1) * 127).astype(np.uint8)
    return rgb, np.ones((alto, ancho), np.float32)


def _medir(nombre: str, funcion, repeticiones: int = 3):
    mejor = float("inf")
    resultado = None
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        resultado = funcion()
        mejor = min(mejor, time.perf_counter() - t0)
    print(f"{nombre:38s} {mejor * 1000:8.0f} ms")
    return resultado, mejor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ancho", type=int, default=3600)
    parser.add_argument("--alto", type=int, default=4800)
    args = parser.parse_args()
    rgb, alpha = _imagen(args.ancho, args.alto)
    marcas = np.zeros(alpha.shape, np.uint8)
    ajustes = HalftoneSettings(quitar_fondo=True)
    completo = (0, 0, args.ancho, args.alto)
    print(f"Imagen {args.ancho}x{args.alto}")

    limpieza, t_limpieza = _medir("E2 limpieza", lambda: cleanup_mask(rgb, alpha, ajustes))
    visible, t_visible = _medir(
        "E2 alfa visible",
        lambda: visible_alpha(alpha, limpieza.eliminado, marcas, ajustes.semitransparencia),
    )
    cov, t_cov = _medir("E3 cobertura", lambda: coverage_map(rgb, visible, marcas, ajustes, NEGRO))
    for patron in (Pattern.REDONDO, Pattern.PUNTOS_ONDULADOS):
        _medir(f"E4 umbral {patron.value}", lambda: threshold_field(completo, HalftoneSettings(patron=patron)))
    sin_rejilla = HalftoneSettings(ajustar_rejilla=False)
    _medir("E4 umbral sin rejilla", lambda: threshold_field(completo, sin_rejilla))
    umbral, t_umbral = _medir("E4 umbral redondo (en caché)", lambda: threshold_field(completo, ajustes))
    _, t_salida = _medir("E5 salida", lambda: compose_output(rgb, cov, umbral, NEGRO, 0.5))

    total = t_limpieza + t_visible + t_cov + t_umbral + t_salida
    print(f"{'Total E2 a E5 (S1 <= 1500 ms)':38s} {total * 1000:8.0f} ms")

    x0, y0 = args.ancho // 4, args.alto // 4
    rect = (x0, y0, x0 + 1920, y0 + 1080)
    sub = (slice(y0, y0 + 1080), slice(x0, x0 + 1920))
    _, t_rect = _medir(
        "Rectángulo 1920x1080 E4+E5 (S2 <= 300)",
        lambda: compose_output(rgb[sub], cov[sub], threshold_field(rect, ajustes), NEGRO, 0.5),
    )
    print("S1", "cumple" if total <= 1.5 else "NO cumple", "| S2", "cumple" if t_rect <= 0.3 else "NO cumple")


if __name__ == "__main__":
    main()
