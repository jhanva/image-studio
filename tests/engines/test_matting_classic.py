import numpy as np

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE, make_trimap
from image_studio.engines.matting_classic import ClassicMatter


def _borde_suave(n: int = 160):
    filas, columnas = np.mgrid[:n, :n]
    radio = np.hypot(filas - n / 2, columnas - n / 2)
    real = np.clip((50 - radio) / 4 + 0.5, 0, 1).astype(np.float32)
    rng = np.random.default_rng(0)
    frente = np.array([200, 60, 40], np.float32)
    fondo = rng.uniform(150, 230, (n, n, 3)).astype(np.float32)
    rgb = (real[..., None] * frente + (1 - real[..., None]) * fondo).astype(np.uint8)
    return rgb, real, (real >= 0.5).astype(np.float32)


def test_mejora_el_borde_frente_al_alfa_grueso():
    rgb, real, grueso = _borde_suave()
    trimap = make_trimap(grueso, banda_px=6)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    banda = trimap == DESCONOCIDO
    assert np.abs(alfa - real)[banda].mean() < 0.5 * np.abs(grueso - real)[banda].mean()


def test_respeta_zonas_seguras():
    rgb, _, grueso = _borde_suave()
    trimap = make_trimap(grueso, banda_px=6)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    assert (alfa[trimap == FRENTE] == 1.0).all()
    assert (alfa[trimap == FONDO] == 0.0).all()
    assert alfa.dtype == np.float32


def test_bloque_sin_frente_conserva_el_grueso():
    rgb = np.full((64, 64, 3), 128, np.uint8)
    trimap = np.full((64, 64), DESCONOCIDO, np.uint8)
    trimap[:, :10] = FONDO
    grueso = np.full((64, 64), 0.3, np.float32)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    assert np.allclose(alfa[:, 20:], 0.3)
