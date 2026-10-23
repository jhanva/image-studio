"""Elegir modelo y dispositivo según el equipo."""

from __future__ import annotations

from dataclasses import dataclass

from image_studio.engines.hardware import Hardware

# VRAM adicional medida el 2026-10-23 en una RTX 3050 con enable_mem_pattern=False
# (7242, 6216 y 1098 MB), redondeada hacia arriba.
VRAM_NECESARIA_MB = {"birefnet": 7500, "birefnet_lite": 6500, "isnet": 1500}


@dataclass(frozen=True)
class Eleccion:
    modelo: str
    dispositivo: str
    """"auto" usa CUDA si está disponible; "cpu" fuerza CPU."""
    descripcion: str


def choose(modelo: str, equipo: Hardware, gpu_fallida: frozenset[str] | set[str] = frozenset()) -> Eleccion:
    if modelo == "auto":
        modelo = "birefnet" if equipo.vram_mb >= VRAM_NECESARIA_MB["birefnet"] else "birefnet_lite"
    if modelo not in VRAM_NECESARIA_MB:
        raise ValueError(f"Modelo no soportado: {modelo}")
    necesaria = VRAM_NECESARIA_MB[modelo]
    if equipo.tiene_nvidia and equipo.vram_mb >= necesaria and modelo not in gpu_fallida:
        return Eleccion(modelo, "auto", f"{modelo} en GPU ({equipo.gpu})")
    if not equipo.tiene_nvidia:
        motivo = "sin GPU NVIDIA"
    elif modelo in gpu_fallida:
        motivo = "la GPU falló antes"
    else:
        motivo = f"la GPU tiene {equipo.vram_mb} MB y el modelo necesita {necesaria} MB"
    return Eleccion(modelo, "cpu", f"{modelo} en CPU ({motivo})")
