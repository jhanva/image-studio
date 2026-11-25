import numpy as np
import pytest

from image_studio.core.halftone.knockout import (
    BLANCO,
    NEGRO,
    auto_knockout,
    clean_edges,
    coverage,
    distance,
    drop_small,
    knockout_color,
    restore_ink,
)
from image_studio.core.halftone.settings import HalftoneSettings


def _px(*colores):
    return np.array([colores], np.uint8)


def test_distancia_en_colores_conocidos():
    d = distance(_px((0, 0, 0), (255, 0, 0), (51, 51, 51), (0, 0, 102)), NEGRO)
    np.testing.assert_allclose(d[0], [0.0, 1.0, 0.2, 0.4], atol=1e-6)
    gris = distance(_px((128, 128, 128), (0, 128, 128), (255, 128, 128)), (128, 128, 128))
    np.testing.assert_allclose(gris[0], [0.0, 1.0, 1.0], atol=1e-6)


def test_s4_el_color_exacto_de_la_camiseta_no_tiene_cobertura():
    for k in (NEGRO, BLANCO, (30, 90, 200)):
        assert coverage(_px(k), k, 1.0, 1.0)[0, 0] == 0.0


def test_cobertura_con_alcance_y_gamma():
    rgb = _px((51, 0, 0), (102, 0, 0), (204, 0, 0))
    np.testing.assert_allclose(coverage(rgb, NEGRO, 1.0, 1.0)[0], [0.2, 0.4, 0.8], atol=1e-6)
    np.testing.assert_allclose(coverage(rgb, NEGRO, 0.5, 1.0)[0], [0.4, 0.8, 1.0], atol=1e-6)
    np.testing.assert_allclose(coverage(rgb, NEGRO, 1.0, 0.5)[0], np.sqrt([0.2, 0.4, 0.8]), atol=1e-6)


def test_s5_descartar_puntos_pequenos():
    cov = np.array([[0.01, 0.029, 0.5, 0.975, 0.99]], np.float32)
    drop_small(cov, 0.03)
    np.testing.assert_allclose(cov[0], [0.0, 0.0, 0.5, 1.0, 1.0])


def test_bordes_limpios_dilata_lo_solido_dentro_de_lo_visible():
    cov = np.full((5, 7), 0.5, np.float32)
    cov[2, 3] = 1.0
    visible = np.ones((5, 7), bool)
    visible[2, 4] = False
    clean_edges(cov, visible, 1)
    assert cov[1, 3] == cov[3, 3] == cov[2, 2] == 1.0
    assert cov[2, 4] == 0.5 and cov[0, 3] == 0.5 and cov[1, 2] == 0.5


def test_restaurar_color_deshace_la_mezcla():
    # Rojo puro al 50% sobre camiseta negra se ve (128, 0, 0).
    rgb = _px((128, 0, 0))
    cov = np.array([[128 / 255]], np.float32)
    assert tuple(restore_ink(rgb, cov, NEGRO, 1.0)[0, 0]) == (255, 0, 0)
    assert tuple(restore_ink(rgb, cov, NEGRO, 0.0)[0, 0]) == (128, 0, 0)
    medio = restore_ink(rgb, cov, NEGRO, 0.5)[0, 0, 0]
    assert 128 < medio < 255


def test_color_automatico_segun_el_marco():
    oscuro = np.full((6, 6, 3), 20, np.uint8)
    claro = np.full((6, 6, 3), 240, np.uint8)
    alfa = np.ones((6, 6), np.float32)
    assert auto_knockout(oscuro, alfa) == NEGRO
    assert auto_knockout(claro, alfa) == BLANCO
    assert knockout_color(HalftoneSettings(knockout="auto"), claro, alfa) == BLANCO
    assert knockout_color(HalftoneSettings(knockout="elegido", color_elegido=(1, 2, 3)), claro, alfa) == (1, 2, 3)


@pytest.mark.parametrize("k", [NEGRO, BLANCO])
def test_cobertura_es_float32_y_no_toca_la_entrada(k):
    rgb = np.random.default_rng(0).integers(0, 256, (10, 10, 3), dtype=np.uint8)
    copia = rgb.copy()
    cov = coverage(rgb, k, 0.7, 1.3)
    assert cov.dtype == np.float32 and 0 <= cov.min() and cov.max() <= 1
    np.testing.assert_array_equal(rgb, copia)
