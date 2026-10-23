"""Segmentación real con los modelos descargados (marca model)."""

import numpy as np
import pytest

from image_studio.core.metrics import iou
from image_studio.engines.model_manager import MODELOS, create_session, models_dir
from image_studio.engines.segment_birefnet import BiRefNetSegmenter
from image_studio.engines.segment_isnet import ISNetSegmenter

pytestmark = pytest.mark.model
CLASES = {"birefnet": BiRefNetSegmenter, "isnet": ISNetSegmenter}


@pytest.fixture(scope="module", params=sorted(CLASES))
def segmentador(request):
    ruta = models_dir() / MODELOS[request.param].archivo
    if not ruta.exists():
        pytest.skip(f"Modelo {request.param} no descargado")
    return CLASES[request.param](create_session(ruta))


def test_segmenta_disco_sobre_fondo_liso(segmentador):
    alto, ancho = 600, 800
    filas, columnas = np.mgrid[:alto, :ancho]
    disco = np.hypot(filas - 300, columnas - 400) <= 180
    rgb = np.full((alto, ancho, 3), 235, np.uint8)
    rgb[disco] = (200, 40, 30)
    alfa = segmentador.predict(rgb)
    assert iou(alfa, disco.astype(np.float32)) >= 0.9
