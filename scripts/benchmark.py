"""Mide el pipeline completo sobre una imagen de 4000x3000 (criterios V4 y V5 de la spec).

Uso: .\\.venv\\Scripts\\python.exe -X utf8 scripts\\benchmark.py RUTA_IMAGEN [--cpu] [--preset persona]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from time import perf_counter

import cv2

from image_studio.core.image_io import load_image
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.settings import PRESETS

TAMANO = (4000, 3000)
LIMITE_S = {"auto": 5.0, "cpu": 60.0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark del pipeline de quitar fondos")
    parser.add_argument("imagen", type=Path)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="persona")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()

    dispositivo = "cpu" if args.cpu else "auto"
    ajustes = PRESETS[args.preset]
    doc = load_image(args.imagen)
    if doc.size != TAMANO:
        doc.rgb = cv2.resize(doc.rgb, TAMANO, interpolation=cv2.INTER_CUBIC)
        doc.alpha = None
    removedor = build_remover(ajustes.modelo, dispositivo)
    removedor.run(doc, ajustes)  # calentamiento: sesión ONNX y compilación de numba

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
