"""Un removedor por modelo y dispositivo, compartido por todas las herramientas."""

from __future__ import annotations

import threading

from image_studio.pipeline.factory import build_remover


class RemoverCache:
    def __init__(self, crear=build_remover):
        self._crear = crear
        self._removedores: dict[tuple[str, str], object] = {}
        # Cargar BiRefNet tarda unos 11 s; el candado evita cargarlo dos veces si el editor y
        # el panel de lotes lo piden a la vez.
        self._candado = threading.Lock()

    def get(self, modelo: str, dispositivo: str = "auto", progreso=None):
        clave = (modelo, dispositivo)
        with self._candado:
            if clave not in self._removedores:
                self._removedores[clave] = self._crear(modelo, dispositivo, progreso)
            return self._removedores[clave]
