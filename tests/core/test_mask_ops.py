import numpy as np
import pytest

from image_studio.core.mask_ops import (
    DESCONOCIDO,
    FONDO,
    FRENTE,
    adjust_edge,
    content_bbox,
    make_trimap,
)


def _cuadro(n: int = 100) -> np.ndarray:
    alfa = np.zeros((n, n), np.float32)
    alfa[30:70, 30:70] = 1.0
    return alfa


def test_trimap_marca_frente_fondo_y_banda():
    trimap = make_trimap(_cuadro(), banda_px=5)
    assert trimap.dtype == np.uint8
    assert trimap[50, 50] == FRENTE
    assert trimap[0, 0] == FONDO
    assert trimap[30, 50] == DESCONOCIDO
    assert trimap[27, 50] == DESCONOCIDO
    assert trimap[20, 50] == FONDO


def test_trimap_marca_valores_inciertos_como_desconocido():
    alfa = np.zeros((50, 50), np.float32)
    alfa[:10, :10] = 0.3
    assert (make_trimap(alfa, banda_px=2)[:10, :10] == DESCONOCIDO).all()


def test_trimap_rechaza_banda_cero():
    with pytest.raises(ValueError):
        make_trimap(_cuadro(), banda_px=0)


def test_desplazamiento_positivo_agranda_y_negativo_achica():
    alfa = _cuadro()
    area = (alfa >= 0.5).sum()
    assert (adjust_edge(alfa, desplazamiento_px=3) >= 0.5).sum() > area
    assert (adjust_edge(alfa, desplazamiento_px=-3) >= 0.5).sum() < area


def test_suavizado_crea_valores_intermedios_en_rango():
    salida = adjust_edge(_cuadro(), suavizado_px=2.0)
    assert ((salida > 0.05) & (salida < 0.95)).any()
    assert salida.min() >= 0.0 and salida.max() <= 1.0
    assert salida.dtype == np.float32


def test_sin_ajustes_devuelve_copia_igual():
    alfa = _cuadro()
    salida = adjust_edge(alfa)
    assert np.array_equal(salida, alfa) and salida is not alfa


def test_caja_de_contenido():
    assert content_bbox(_cuadro()) == (30, 30, 70, 70)
    assert content_bbox(np.zeros((10, 10), np.float32)) is None
