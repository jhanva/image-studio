from pathlib import Path

import numpy as np
import pytest

from image_studio.core.image_io import ImageDoc
from image_studio.pipeline.remove_bg import BackgroundRemover, evaluate_confidence
from image_studio.pipeline.settings import PipelineSettings

SIN_EXTRAS = PipelineSettings(matting=False, limpieza_color=False)


class SegmentadorFalso:
    nombre = "falso"

    def __init__(self, alfa):
        self.alfa = alfa
        self.llamadas = 0

    def predict(self, rgb):
        self.llamadas += 1
        return self.alfa.copy()


class MatterFalso:
    nombre = "falso"

    def __init__(self):
        self.trimap = None

    def refine(self, rgb, trimap, grueso):
        self.trimap = trimap
        return grueso * 0.9


def _cuadro(n: int = 100):
    alfa = np.zeros((n, n), np.float32)
    alfa[30:70, 30:70] = 1.0
    return alfa


def _doc(alfa_archivo=None, n: int = 100):
    return ImageDoc(Path("x.png"), np.full((n, n, 3), 128, np.uint8), alfa_archivo, None, None)


def test_sin_matting_devuelve_el_alfa_del_segmentador():
    matter = MatterFalso()
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro()), matter).run(_doc(), SIN_EXTRAS)
    assert matter.trimap is None and resultado.trimap is None
    assert np.array_equal(resultado.alpha, _cuadro())
    assert "segmentacion" in resultado.tiempos


def test_con_matting_usa_trimap_y_motor():
    matter = MatterFalso()
    ajustes = PipelineSettings(matting=True, limpieza_color=False, banda_px=4)
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro()), matter).run(_doc(), ajustes)
    assert matter.trimap is not None and resultado.trimap is matter.trimap
    assert np.allclose(resultado.alpha, _cuadro() * 0.9)


def test_matting_sin_motor_falla():
    with pytest.raises(ValueError, match="matting"):
        BackgroundRemover(SegmentadorFalso(_cuadro())).run(_doc(), PipelineSettings(limpieza_color=False))


def test_usa_alfa_existente_sin_segmentar():
    segmentador = SegmentadorFalso(_cuadro())
    resultado = BackgroundRemover(segmentador).run(
        _doc(alfa_archivo=_cuadro() * 0.5), SIN_EXTRAS, usar_alfa_existente=True
    )
    assert segmentador.llamadas == 0
    assert np.allclose(resultado.alpha, _cuadro() * 0.5)


def test_limpieza_de_color_conserva_forma():
    ajustes = PipelineSettings(matting=False, limpieza_color=True, suavizado_px=2.0)
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro())).run(_doc(), ajustes)
    assert resultado.rgb.shape == (100, 100, 3) and resultado.rgb.dtype == np.uint8


def test_confianza():
    assert evaluate_confidence(_cuadro()) == (False, "")
    baja, motivo = evaluate_confidence(np.zeros((100, 100), np.float32))
    assert baja and "pequeño" in motivo
    baja, motivo = evaluate_confidence(np.ones((100, 100), np.float32))
    assert baja and "casi toda" in motivo
    baja, motivo = evaluate_confidence(np.full((100, 100), 0.5, np.float32))
    assert baja and "incierto" in motivo
