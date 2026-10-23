from types import SimpleNamespace

import numpy as np

from image_studio.engines.segment_birefnet import BiRefNetSegmenter
from image_studio.engines.segment_isnet import ISNetSegmenter


class SesionFalsa:
    def __init__(self, salida: np.ndarray):
        self.salida = salida
        self.recibido = None

    def get_inputs(self):
        return [SimpleNamespace(name="input_image")]

    def run(self, _salidas, entradas):
        self.recibido = entradas["input_image"]
        return [self.salida]


def test_birefnet_normaliza_y_devuelve_tamano_original():
    sesion = SesionFalsa(np.zeros((1, 1, 1024, 1024), np.float32))
    rgb = np.empty((200, 300, 3), np.uint8)
    rgb[...] = (124, 116, 104)
    alfa = BiRefNetSegmenter(sesion).predict(rgb)
    assert sesion.recibido.shape == (1, 3, 1024, 1024)
    assert sesion.recibido.dtype == np.float32
    assert np.abs(sesion.recibido).max() < 0.01
    assert alfa.shape == (200, 300)
    assert np.allclose(alfa, 0.5)


def test_birefnet_aplica_sigmoide():
    logits = np.full((1, 1, 1024, 1024), -20.0, np.float32)
    logits[..., :512] = 20.0
    alfa = BiRefNetSegmenter(SesionFalsa(logits)).predict(np.zeros((64, 64, 3), np.uint8))
    assert alfa[:, :20].min() > 0.99
    assert alfa[:, 44:].max() < 0.01


def test_isnet_normaliza_min_max():
    mapa = np.full((1, 1, 1024, 1024), 2.0, np.float32)
    mapa[..., :512] = 4.0
    alfa = ISNetSegmenter(SesionFalsa(mapa)).predict(np.zeros((64, 64, 3), np.uint8))
    assert alfa.max() == 1.0 and alfa.min() == 0.0


def test_isnet_usa_media_0_5():
    sesion = SesionFalsa(np.zeros((1, 1, 1024, 1024), np.float32))
    rgb = np.full((32, 32, 3), 128, np.uint8)
    ISNetSegmenter(sesion).predict(rgb)
    assert np.abs(sesion.recibido).max() < 0.01
