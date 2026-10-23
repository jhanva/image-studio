"""Detección del equipo: GPU NVIDIA y su memoria, RAM y núcleos."""

from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Hardware:
    gpu: str | None
    vram_mb: int
    ram_mb: int
    cpus: int

    @property
    def tiene_nvidia(self) -> bool:
        return self.gpu is not None and self.vram_mb > 0

    def describir(self) -> str:
        ram = f"{self.ram_mb / 1024:.0f} GB de RAM"
        if self.tiene_nvidia:
            return f"{self.gpu} ({self.vram_mb / 1024:.0f} GB), {ram}"
        return f"Sin GPU NVIDIA, {ram}, {self.cpus} núcleos"


def parse_nvidia_smi(salida: str) -> tuple[str | None, int]:
    """Primera GPU de las líneas 'nombre, memoria_mb'; (None, 0) si no hay ninguna válida."""
    for linea in salida.strip().splitlines():
        partes = [p.strip() for p in linea.rsplit(",", 1)]
        if len(partes) == 2 and partes[1].isdigit():
            return partes[0], int(partes[1])
    return None, 0


def _consultar_nvidia_smi() -> str:
    # nvidia-smi viene con el driver; si no está, el equipo no tiene GPU NVIDIA utilizable.
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return resultado.stdout if resultado.returncode == 0 else ""


class _EstadoMemoria(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _ram_mb() -> int:
    estado = _EstadoMemoria()
    estado.dwLength = ctypes.sizeof(estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        return 0
    return int(estado.ullTotalPhys // 2**20)


def detect_hardware(consultar=_consultar_nvidia_smi) -> Hardware:
    gpu, vram = parse_nvidia_smi(consultar())
    return Hardware(gpu, vram, _ram_mb(), os.cpu_count() or 1)
