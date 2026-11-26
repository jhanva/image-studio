"""Línea de comandos de mantenimiento: preparar el motor y diagnosticar el equipo."""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np

from image_studio import __version__
from image_studio.core.image_io import ImageDoc
from image_studio.engines.hardware import Hardware, detect_hardware
from image_studio.engines.model_manager import MODELOS, available_providers, models_dir
from image_studio.engines.warmup import prepare_engines
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.settings import PRESETS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image_studio", description="Image Studio")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("preparar", help="Compilar el motor de matting (lo usa el instalador)")
    comandos.add_parser("diagnostico", help="Mostrar el equipo, la elección automática y probar el motor")
    return parser


def main(argv: list[str] | None = None, crear_removedor=build_remover, hardware: Hardware | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.comando == "preparar":
        print(f"Motor listo en {prepare_engines():.1f} s")
        return 0
    return _diagnostico(hardware or detect_hardware(), crear_removedor)


def _diagnostico(equipo: Hardware, crear_removedor) -> int:
    print(f"Image Studio {__version__} en Python {platform.python_version()}")
    print(f"Ejecutable: {'sí' if getattr(sys, 'frozen', False) else 'no'}")
    print(f"Equipo: {equipo.describir()}")
    print(f"Proveedores ONNX: {', '.join(available_providers())}")
    eleccion = choose("auto", equipo)
    print(f"Automático: {eleccion.descripcion}")
    print(f"Motor de matting listo en {prepare_engines():.1f} s")
    if not (models_dir() / MODELOS[eleccion.modelo].archivo).exists():
        print(f"Modelo {eleccion.modelo} no descargado: se descargará al primer uso")
        return 0
    cache = RemoverCache(crear_removedor, hardware=equipo)
    filas, columnas = np.mgrid[:600, :800]
    rgb = np.full((600, 800, 3), 235, np.uint8)
    rgb[np.hypot(filas - 300, columnas - 400) <= 180] = (200, 40, 30)
    ajustes = replace(PRESETS["persona"], modelo="auto")
    inicio = perf_counter()
    resultado = cache.run(ImageDoc(Path("diagnostico.png"), rgb, None, None, None), ajustes)
    print(f"Prueba de recorte: {perf_counter() - inicio:.1f} s con {resultado.dispositivo}, alfa medio {resultado.alpha.mean():.3f}")
    return 0
