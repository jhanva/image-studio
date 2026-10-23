"""Línea de comandos: python -m image_studio batch ENTRADA SALIDA [opciones]."""

from __future__ import annotations

import argparse
import platform
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np

from image_studio import __version__
from image_studio.core.export import FORMATOS_SALIDA, ExportSettings, Fondo
from image_studio.core.image_io import ImageDoc
from image_studio.engines.hardware import Hardware, detect_hardware
from image_studio.engines.model_manager import MODELOS, available_providers, models_dir
from image_studio.engines.warmup import prepare_engines
from image_studio.pipeline.batch import BatchItem, run_batch
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.settings import MODELOS_SEGMENTACION, PRESETS


def color_hex(valor: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
        raise argparse.ArgumentTypeError(f"Color inválido: {valor} (usar #RRGGBB)")
    return tuple(int(valor[i : i + 2], 16) for i in (1, 3, 5))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image_studio", description="Image Studio")
    comandos = parser.add_subparsers(dest="comando", required=True)
    lote = comandos.add_parser("batch", help="Quitar el fondo de todas las imágenes de una carpeta")
    lote.add_argument("entrada", type=Path)
    lote.add_argument("salida", type=Path)
    lote.add_argument("--preset", choices=sorted(PRESETS), default="producto")
    lote.add_argument("--modelo", choices=MODELOS_SEGMENTACION, help="Sustituye el modelo del preset")
    lote.add_argument("--formato", choices=sorted(FORMATOS_SALIDA), default="png")
    lote.add_argument("--fondo", choices=[f.value for f in Fondo], default=Fondo.TRANSPARENTE.value)
    lote.add_argument("--color", type=color_hex, default=(255, 255, 255), help="#RRGGBB para --fondo color")
    lote.add_argument("--recortar", action="store_true", help="Recortar al contenido")
    lote.add_argument("--margen", type=int, default=0, help="Margen en px al recortar")
    lote.add_argument("--dpi", type=int)
    lote.add_argument("--cpu", action="store_true", help="Forzar CPU")
    comandos.add_parser("preparar", help="Compilar el motor de matting (lo usa el instalador)")
    comandos.add_parser("diagnostico", help="Mostrar el equipo, la elección automática y probar el motor")
    return parser


def main(argv: list[str] | None = None, crear_removedor=build_remover, hardware: Hardware | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.comando == "preparar":
        print(f"Motor listo en {prepare_engines():.1f} s")
        return 0
    if args.comando == "diagnostico":
        return _diagnostico(hardware or detect_hardware(), crear_removedor)
    if not args.entrada.is_dir():
        print(f"La carpeta de entrada no existe: {args.entrada}", file=sys.stderr)
        return 2
    ajustes = PRESETS[args.preset]
    if args.modelo:
        ajustes = replace(ajustes, modelo=args.modelo)
    exportar = ExportSettings(
        formato=args.formato,
        fondo=Fondo(args.fondo),
        color=args.color,
        recortar=args.recortar,
        margen_px=args.margen,
        dpi=args.dpi,
    )
    equipo = hardware or detect_hardware()
    if args.cpu:
        equipo = replace(equipo, gpu=None, vram_mb=0)
    print(f"Usando {choose(ajustes.modelo, equipo).descripcion}" + (" (forzado a CPU)" if args.cpu else ""))
    # El caché resuelve el modelo automático y sigue en CPU si la GPU no responde.
    removedor = RemoverCache(lambda m, d, p: crear_removedor(m, d, _progreso_descarga), hardware=equipo)
    items = run_batch(args.entrada, args.salida, removedor, ajustes, exportar, progreso=_progreso_lote)
    conteo = Counter(item.estado for item in items)
    print(
        f"Listo: {conteo['ok']} ok, {conteo['baja_confianza']} baja confianza, "
        f"{conteo['error']} con error. Informe: {args.salida / 'informe.csv'}"
    )
    return 1 if conteo["error"] else 0


def _progreso_descarga(leidos: int, total: int) -> None:
    print(f"\rDescargando modelo: {leidos * 100 // max(total, 1)}%", end="", flush=True)
    if leidos >= total:
        print()


def _progreso_lote(hechos: int, total: int, item: BatchItem) -> None:
    detalle = f" ({item.motivo})" if item.motivo else ""
    print(f"[{hechos}/{total}] {item.archivo.name}: {item.estado}{detalle}")


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
