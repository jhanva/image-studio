"""Mide el pipeline completo sobre una imagen de 4000x3000 (criterios V4 y V5 de la spec).

Uso: .\\.venv\\Scripts\\python.exe -X utf8 scripts\\benchmark.py RUTA_IMAGEN [--cpu] [--preset persona]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from time import perf_counter

from dataclasses import replace

import cv2
import numpy as np

from image_studio.core.image_io import load_image
from image_studio.engines.hardware import detect_hardware
from image_studio.core.mask_ops import DESCONOCIDO, make_trimap
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.refine_region import refine_region, region_bbox
from image_studio.pipeline.settings import PRESETS

TAMANO = (4000, 3000)
LIMITE_S = {"auto": 5.0, "cpu": 60.0}
LIMITE_REFINAR_S = 2.0
LADO_REGION = 500


def medir_refinado(removedor, doc, ajustes) -> float:
    """V6: refinar una región de 500x500 pintada sobre el borde del sujeto."""
    alfa = removedor.run(doc, replace(ajustes, matting=False, limpieza_color=False)).alpha.copy()
    banda = make_trimap(alfa, 20) == DESCONOCIDO
    filas, columnas = np.nonzero(banda)
    cy, cx = int(filas[len(filas) // 2]), int(columnas[len(columnas) // 2])
    y0, x0 = max(0, cy - LADO_REGION // 2), max(0, cx - LADO_REGION // 2)
    pintado = np.zeros_like(banda)
    pintado[y0 : y0 + LADO_REGION, x0 : x0 + LADO_REGION] = banda[y0 : y0 + LADO_REGION, x0 : x0 + LADO_REGION]
    caja = region_bbox(pintado)
    matter = ClassicMatter()
    refine_region(doc.rgb, alfa.copy(), pintado, matter, caja)  # calentamiento
    inicio = perf_counter()
    refine_region(doc.rgb, alfa, pintado, matter, caja)
    return perf_counter() - inicio


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark del pipeline de quitar fondos")
    parser.add_argument("imagen", type=Path)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="persona")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--refinar", action="store_true", help="Medir V6 (refinar 500x500)")
    args = parser.parse_args()

    dispositivo = "cpu" if args.cpu else "auto"
    ajustes = PRESETS[args.preset]
    doc = load_image(args.imagen)
    if doc.size != TAMANO:
        doc.rgb = cv2.resize(doc.rgb, TAMANO, interpolation=cv2.INTER_CUBIC)
        doc.alpha = None
    eleccion = choose(ajustes.modelo, detect_hardware())
    ajustes = replace(ajustes, modelo=eleccion.modelo)
    print(f"Usando {eleccion.descripcion}")
    removedor = build_remover(ajustes.modelo, "cpu" if args.cpu else eleccion.dispositivo)
    removedor.run(doc, ajustes)  # calentamiento: sesión ONNX y compilación de numba
    if args.refinar:
        segundos = medir_refinado(removedor, doc, ajustes)
        estado = "OK" if segundos <= LIMITE_REFINAR_S else "FUERA DE LIMITE"
        print(f"refinar {LADO_REGION}x{LADO_REGION}: {segundos:.2f}s, limite {LIMITE_REFINAR_S:.0f}s: {estado}")
        return 0 if segundos <= LIMITE_REFINAR_S else 1

    tiempos = []
    for i in range(args.repeticiones):
        inicio = perf_counter()
        resultado = removedor.run(doc, ajustes)
        tiempos.append(perf_counter() - inicio)
        etapas = ", ".join(f"{k} {v:.2f}s" for k, v in resultado.tiempos.items())
        print(f"corrida {i + 1}: {tiempos[-1]:.2f}s ({etapas})")
    mediana = statistics.median(tiempos)
    limite = LIMITE_S[dispositivo]
    estado = "OK" if mediana <= limite else "FUERA DE LIMITE"
    print(f"mediana {mediana:.2f}s, limite {limite:.0f}s ({dispositivo}): {estado}")
    return 0 if mediana <= limite else 1


if __name__ == "__main__":
    sys.exit(main())
