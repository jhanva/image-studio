"""Presets propios guardados en la carpeta de configuración del usuario."""

from __future__ import annotations

import json
import os
from pathlib import Path

from image_studio.pipeline.settings import PRESETS, PipelineSettings

VERSION = 1


def config_dir() -> Path:
    personalizado = os.environ.get("IMAGE_STUDIO_CONFIG_DIR")
    if personalizado:
        return Path(personalizado)
    return Path(os.environ["APPDATA"]) / "ImageStudio"


class PresetStore:
    """Presets incluidos más los propios del usuario. Las subclases cambian tipo, incluidos y archivo."""

    ARCHIVO = "presets.json"
    INCLUIDOS: dict = PRESETS
    TIPO = PipelineSettings

    def __init__(self, ruta: Path | None = None):
        self.ruta = ruta or config_dir() / self.ARCHIVO

    def todos(self) -> dict:
        """Incluidos primero, luego los propios en orden alfabético."""
        return {**self.INCLUIDOS, **dict(sorted(self.propios().items()))}

    def propios(self) -> dict:
        propios = {}
        for nombre, datos in self._leer().items():
            try:
                propios[nombre] = self.TIPO.from_dict(datos)
            except (TypeError, ValueError):
                continue  # una entrada editada a mano o de una versión vieja no impide abrir la app
        return propios

    def guardar(self, nombre: str, ajustes) -> str:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El preset necesita un nombre")
        if nombre in self.INCLUIDOS:
            raise ValueError(f"'{nombre}' es un preset incluido")
        datos = self._leer()
        datos[nombre] = ajustes.to_dict()
        self._escribir(datos)
        return nombre

    def borrar(self, nombre: str) -> None:
        if nombre in self.INCLUIDOS:
            raise ValueError(f"'{nombre}' es un preset incluido")
        datos = self._leer()
        datos.pop(nombre, None)
        self._escribir(datos)

    def _leer(self) -> dict:
        try:
            contenido = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        presets = contenido.get("presets") if isinstance(contenido, dict) else None
        if not isinstance(presets, dict):
            return {}
        return {k: v for k, v in presets.items() if isinstance(v, dict)}

    def _escribir(self, presets: dict) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_name(self.ruta.name + ".tmp")
        texto = json.dumps({"version": VERSION, "presets": presets}, ensure_ascii=False, indent=2)
        temporal.write_text(texto + "\n", encoding="utf-8", newline="\n")
        temporal.replace(self.ruta)
