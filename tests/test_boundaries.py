"""V10: core, engines y pipeline no pueden importar Qt."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "image_studio"
CAPAS_SIN_QT = ("core", "engines", "pipeline")
PROHIBIDOS = {"PySide6", "shiboken6"}


def _archivos() -> list[Path]:
    return sorted(p for capa in CAPAS_SIN_QT for p in (SRC / capa).rglob("*.py"))


def _modulos_importados(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    modulos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.append(nodo.module)
    return modulos


def test_hay_archivos_que_revisar():
    assert _archivos()


@pytest.mark.parametrize("ruta", _archivos(), ids=lambda p: p.relative_to(SRC).as_posix())
def test_capa_no_importa_qt(ruta):
    prohibidos = [m for m in _modulos_importados(ruta) if m.split(".")[0] in PROHIBIDOS]
    assert not prohibidos, f"{ruta.name} importa {prohibidos}"
