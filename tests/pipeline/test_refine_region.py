import numpy as np

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.refine_region import refine_region, region_bbox


class MatterFijo:
    nombre = "fijo"

    def __init__(self):
        self.trimap = None

    def refine(self, rgb, trimap, grueso):
        self.trimap = trimap
        return np.full(grueso.shape, 0.42, np.float32)


def _medio_y_medio(n: int = 100):
    alfa = np.zeros((n, n), np.float32)
    alfa[:, n // 2 :] = 1.0
    pintado = np.zeros((n, n), bool)
    pintado[40:60, 45:55] = True
    return alfa, pintado


def test_caja_de_la_region():
    _, pintado = _medio_y_medio()
    assert region_bbox(pintado, margen=8) == (37, 32, 63, 68)
    assert region_bbox(np.zeros((10, 10), bool)) is None


def test_solo_cambia_lo_pintado():
    alfa, pintado = _medio_y_medio()
    caja = region_bbox(pintado, margen=8)
    rect = refine_region(np.zeros((100, 100, 3), np.uint8), alfa, pintado, MatterFijo(), caja)
    assert rect == caja
    assert np.allclose(alfa[pintado], 0.42)
    assert alfa[0, 0] == 0.0 and alfa[0, 99] == 1.0


def test_trimap_desconocido_solo_en_lo_pintado():
    alfa, pintado = _medio_y_medio()
    matter = MatterFijo()
    caja = region_bbox(pintado, margen=8)
    refine_region(np.zeros((100, 100, 3), np.uint8), alfa, pintado, matter, caja)
    x0, y0, x1, y1 = caja
    assert ((matter.trimap == DESCONOCIDO) == pintado[y0:y1, x0:x1]).all()
    assert matter.trimap[0, 0] == FONDO and matter.trimap[0, -1] == FRENTE


def test_matting_real_mejora_el_borde():
    n = 200
    filas, columnas = np.mgrid[:n, :n]
    real = np.clip((columnas - 100 + 20 * np.sin(filas / 15)) / 5 + 0.5, 0, 1).astype(np.float32)
    rng = np.random.default_rng(0)
    rgb = (real[..., None] * np.array([90, 60, 40]) + (1 - real[..., None]) * rng.uniform(150, 230, (n, n, 3))).astype(np.uint8)
    alfa = (real >= 0.5).astype(np.float32)
    grueso = alfa.copy()
    pintado = (real > 0.02) & (real < 0.98)
    refine_region(rgb, alfa, pintado, ClassicMatter(tile=64, margen=16), region_bbox(pintado))
    assert np.abs(alfa - real)[pintado].mean() < np.abs(grueso - real)[pintado].mean()
