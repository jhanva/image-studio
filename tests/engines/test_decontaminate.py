import numpy as np

from image_studio.engines.decontaminate import decontaminate


def _degradado(n: int = 64):
    alfa = np.zeros((n, n), np.float32)
    alfa[:, :28] = 1.0
    alfa[:, 28:36] = np.linspace(1.0, 0.0, 8, dtype=np.float32)
    frente, fondo = np.array([220, 30, 30], np.float32), np.array([30, 30, 220], np.float32)
    rgb = (alfa[..., None] * frente + (1 - alfa[..., None]) * fondo).astype(np.uint8)
    return rgb, alfa


def test_recupera_el_color_del_frente_en_el_borde():
    rgb, alfa = _degradado()
    limpio = decontaminate(rgb, alfa)
    borde = (alfa > 0.2) & (alfa < 0.8)
    assert limpio[borde][:, 0].mean() > rgb[borde][:, 0].mean() + 30
    assert np.array_equal(limpio[alfa >= 0.99], rgb[alfa >= 0.99])


def test_sin_borde_devuelve_copia():
    rgb = np.full((16, 16, 3), 90, np.uint8)
    alfa = np.ones((16, 16), np.float32)
    limpio = decontaminate(rgb, alfa)
    assert np.array_equal(limpio, rgb) and limpio is not rgb


def test_hilos_dan_el_mismo_resultado_que_secuencial():
    rgb, alfa = _degradado(n=600)
    secuencial = decontaminate(rgb, alfa, tile=128, hilos=1)
    paralelo = decontaminate(rgb, alfa, tile=128, hilos=4)
    assert np.array_equal(secuencial, paralelo)


def test_numba_usa_una_capa_segura_para_hilos():
    import numba

    assert numba.config.THREADING_LAYER == "threadsafe"
