from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def escribir_png():
    """Crea un PNG RGB sintético y devuelve su ruta."""

    def _escribir(ruta: Path, ancho: int = 8, alto: int = 8, color=(200, 40, 30)) -> Path:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((alto, ancho, 3), color, np.uint8)).save(ruta)
        return ruta

    return _escribir
