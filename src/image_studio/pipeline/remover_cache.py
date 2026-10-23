"""Un removedor por modelo y dispositivo, compartido por todas las herramientas."""

from __future__ import annotations

import threading
from dataclasses import replace

from image_studio.engines.hardware import Hardware, detect_hardware
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.factory import build_remover


class RemoverCache:
    def __init__(self, crear=build_remover, hardware: Hardware | None = None):
        self._crear = crear
        self._hardware = hardware
        self._removedores: dict[tuple[str, str], object] = {}
        self._gpu_fallida: set[str] = set()
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
        """Resuelve el modelo automático, corre en GPU si conviene y, si la GPU falla, repite en CPU."""
        eleccion = choose(ajustes.modelo, self.hardware, self._gpu_fallida)
        ajustes = replace(ajustes, modelo=eleccion.modelo)
        if eleccion.dispositivo != "cpu":
            try:
                resultado = self.get(eleccion.modelo, eleccion.dispositivo).run(doc, ajustes, usar_alfa_existente)
                return replace(resultado, dispositivo=eleccion.descripcion)
            except Exception:  # memoria de video insuficiente, driver viejo o DLL de CUDA ausentes
                self._gpu_fallida.add(eleccion.modelo)
                eleccion = choose(eleccion.modelo, self.hardware, self._gpu_fallida)
        resultado = self.get(eleccion.modelo, "cpu").run(doc, ajustes, usar_alfa_existente)
        return replace(resultado, dispositivo=eleccion.descripcion)
