import os

# Los tests de interfaz corren sin ventana visible; debe fijarse antes de crear la QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from image_studio.pipeline.remove_bg import RemovalResult


@pytest.fixture
def escribir_png():
    """Crea un PNG RGB sintético y devuelve su ruta."""

    def _escribir(ruta: Path, ancho: int = 8, alto: int = 8, color=(200, 40, 30)) -> Path:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((alto, ancho, 3), color, np.uint8)).save(ruta)
        return ruta

    return _escribir


class RemovedorFalso:
    """Devuelve un alfa casi completo sin cargar modelos."""

    def run(self, doc, ajustes, usar_alfa_existente=False):
        alfa = np.ones(doc.rgb.shape[:2], np.float32)
        alfa[0, 0] = 0.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {})


@pytest.fixture
def removedor_falso():
    return RemovedorFalso()


@pytest.fixture(autouse=True)
def config_temporal(tmp_path, monkeypatch):
    """Ningún test escribe en el %APPDATA% real."""
    monkeypatch.setenv("IMAGE_STUDIO_CONFIG_DIR", str(tmp_path / "config"))
