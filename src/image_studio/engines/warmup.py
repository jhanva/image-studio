"""Preparar el motor: importar pymatting para que numba compile (o lea su caché)."""

from __future__ import annotations

from time import perf_counter


def prepare_engines() -> float:
    """Devuelve los segundos que tardó; unos 40 s la primera vez en un equipo nuevo y menos de 1 s después."""
    from image_studio.engines import decontaminate, matting_classic

    inicio = perf_counter()
    matting_classic._cargar_pymatting()
    decontaminate._cargar_pymatting()
    return perf_counter() - inicio
