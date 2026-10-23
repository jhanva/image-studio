import numpy as np
import pytest

from image_studio.core.brush import (
    Modo,
    brush_profile,
    footprint_rect,
    stamp,
    stroke_points,
    union,
)


def test_huella_suave():
    huella = brush_profile(10, 0.5)
    assert huella.shape == (21, 21) and huella.dtype == np.float32
    assert huella[10, 10] == 1.0
    assert huella[0, 0] == 0.0
    assert huella[10, 2] == pytest.approx(0.4)


def test_huella_dura_es_binaria():
    assert set(np.unique(brush_profile(5, 1.0))) <= {0.0, 1.0}


def test_parametros_invalidos():
    with pytest.raises(ValueError):
        brush_profile(0, 0.5)
    with pytest.raises(ValueError):
        brush_profile(5, 1.5)


def test_rectangulo_de_la_huella():
    huella = brush_profile(5, 1.0)
    assert footprint_rect(25, 25, huella, (50, 50)) == (20, 20, 31, 31)
    assert footprint_rect(0, 0, huella, (50, 50)) == (0, 0, 6, 6)
    assert footprint_rect(-50, -50, huella, (50, 50)) is None


def test_conservar_sube_el_alfa():
    mascara = np.full((50, 50), 0.3, np.float32)
    assert stamp(mascara, 25, 25, brush_profile(5, 1.0), Modo.CONSERVAR) == (20, 20, 31, 31)
    assert mascara[25, 25] == 1.0 and mascara[0, 0] == pytest.approx(0.3)


def test_borrar_baja_el_alfa():
    mascara = np.ones((50, 50), np.float32)
    stamp(mascara, 25, 25, brush_profile(5, 1.0), Modo.BORRAR)
    assert mascara[25, 25] == 0.0 and mascara[0, 0] == 1.0


def test_refinar_no_se_estampa():
    with pytest.raises(ValueError):
        stamp(np.ones((10, 10), np.float32), 5, 5, brush_profile(2, 1.0), Modo.REFINAR)


def test_puntos_del_trazo():
    puntos = stroke_points((0, 0), (10, 0), paso=2.5)
    assert len(puntos) == 4 and puntos[-1] == (10.0, 0.0)


def test_union_de_rectangulos():
    assert union(None, (1, 1, 2, 2)) == (1, 1, 2, 2)
    assert union((0, 0, 5, 5), (3, 3, 8, 9)) == (0, 0, 8, 9)
    assert union(None, None) is None
