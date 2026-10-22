"""Procesamiento por lotes con informe CSV."""

from __future__ import annotations

import csv
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from image_studio.core.export import ExportSettings, compose, save
from image_studio.core.image_io import FORMATOS_ENTRADA, load_image
from image_studio.pipeline.remove_bg import BackgroundRemover
from image_studio.pipeline.settings import PipelineSettings

NOMBRE_INFORME = "informe.csv"


@dataclass
class BatchItem:
    archivo: Path
    estado: str
    """Uno de: ok, baja_confianza, error."""
    tiempo_s: float
    motivo: str
    salida: Path | None


ProgresoLote = Callable[[int, int, BatchItem], None]


def list_images(carpeta: Path) -> list[Path]:
    return sorted(
        p for p in Path(carpeta).iterdir() if p.is_file() and p.suffix.lower() in FORMATOS_ENTRADA
    )


def run_batch(
    entrada: Path,
    salida: Path,
    removedor: BackgroundRemover,
    ajustes: PipelineSettings,
    exportar: ExportSettings,
    progreso: ProgresoLote | None = None,
    cancelar: threading.Event | None = None,
) -> list[BatchItem]:
    salida = Path(salida)
    archivos = list_images(entrada)
    usados: set[str] = set()
    items: list[BatchItem] = []
    for archivo in archivos:
        if cancelar is not None and cancelar.is_set():
            break
        inicio = perf_counter()
        destino = None
        try:
            doc = load_image(archivo)
            resultado = removedor.run(doc, ajustes)
            imagen = compose(resultado.rgb, resultado.alpha, exportar)
            nombre = _nombre_libre(archivo, exportar, usados)
            destino = save(imagen, salida / nombre, exportar, doc.icc_profile)
            estado = "baja_confianza" if resultado.baja_confianza else "ok"
            motivo = resultado.motivo_confianza
        except Exception as exc:  # un archivo con problemas no detiene el lote (V11)
            estado, motivo = "error", str(exc)
        items.append(BatchItem(archivo, estado, perf_counter() - inicio, motivo, destino))
        if progreso is not None:
            progreso(len(items), len(archivos), items[-1])
    write_report(items, salida / NOMBRE_INFORME)
    return items


def write_report(items: list[BatchItem], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["archivo", "estado", "tiempo_s", "motivo", "salida"])
        for item in items:
            escritor.writerow([
                item.archivo.name,
                item.estado,
                f"{item.tiempo_s:.3f}",
                item.motivo,
                item.salida.name if item.salida else "",
            ])


def _nombre_libre(archivo: Path, exportar: ExportSettings, usados: set[str]) -> str:
    nombre = f"{archivo.stem}.{exportar.formato}"
    if nombre.lower() in usados:
        nombre = f"{archivo.stem}_{archivo.suffix.lstrip('.').lower()}.{exportar.formato}"
    usados.add(nombre.lower())
    return nombre
