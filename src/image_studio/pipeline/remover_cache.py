"""Un removedor por modelo y dispositivo, compartido por todas las herramientas."""

from __future__ import annotations

import threading
from dataclasses import replace

from image_studio.engines.hardware import Hardware, detect_hardware
from image_studio.pipeline.device_choice import Eleccion, choose
from image_studio.pipeline.factory import build_remover


def proveedor_real(removedor) -> str | None:
    """Proveedor de ONNX Runtime que usa el removedor, o None si no se puede saber."""
    return getattr(getattr(removedor, "segmentador", None), "proveedor", None)


class RemoverCache:
    def __init__(self, crear=build_remover, hardware: Hardware | None = None):
        self._crear = crear
        self._hardware = hardware
        self._removedores: dict[tuple[str, str], object] = {}
        self._gpu_no_responde = False
        # Cargar BiRefNet tarda unos 11 s; el candado evita cargarlo dos veces si el editor y
        # el panel de lotes lo piden a la vez.
        self._candado = threading.Lock()

    @property
    def hardware(self) -> Hardware:
        with self._candado:
            if self._hardware is None:
                self._hardware = detect_hardware()
            return self._hardware

    def get(self, modelo: str, dispositivo: str = "auto", progreso=None):
        clave = (modelo, dispositivo)
        with self._candado:
            if clave not in self._removedores:
                self._removedores[clave] = self._crear(modelo, dispositivo, progreso)
            return self._removedores[clave]

    def run(self, doc, ajustes, usar_alfa_existente: bool = False):
        """Resuelve el modelo automático, corre en GPU si conviene y, si la GPU no responde, sigue en CPU."""
        eleccion = self._elegir(ajustes.modelo)
        if eleccion.dispositivo != "cpu":
            removedor = self.get(eleccion.modelo, eleccion.dispositivo)
            if proveedor_real(removedor) == "CPUExecutionProvider":
                self._gpu_no_responde = True  # ONNX Runtime cayó a CPU sin lanzar error
            else:
                try:
                    resultado = removedor.run(doc, replace(ajustes, modelo=eleccion.modelo), usar_alfa_existente)
                    return replace(resultado, dispositivo=eleccion.descripcion)
                except Exception:  # memoria de video insuficiente, driver viejo o DLL de CUDA ausentes
                    self._gpu_no_responde = True
            eleccion = self._elegir(ajustes.modelo)
        removedor = self.get(eleccion.modelo, "cpu")
        resultado = removedor.run(doc, replace(ajustes, modelo=eleccion.modelo), usar_alfa_existente)
        return replace(resultado, dispositivo=eleccion.descripcion)

    def _elegir(self, modelo: str) -> Eleccion:
        if not self._gpu_no_responde:
            return choose(modelo, self.hardware)
        # Con la GPU fuera de juego se elige como en un equipo sin GPU (modelo liviano si es automático).
        eleccion = choose(modelo, replace(self.hardware, gpu=None, vram_mb=0))
        return replace(eleccion, descripcion=f"{eleccion.modelo} en CPU (la GPU no respondió)")
