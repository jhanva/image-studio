import numpy as np

from image_studio.core.halftone.knockout import NEGRO
from image_studio.core.halftone.render import (
    BORRAR,
    PROTEGER,
    compose_output,
    coverage_map,
    render,
    visible_alpha,
)
from image_studio.core.halftone.settings import AlphaMode, HalftoneSettings


def _degradado(alto=64, ancho=256):
    rgb = np.zeros((alto, ancho, 3), np.uint8)
    rgb[..., 0] = np.linspace(0, 255, ancho).astype(np.uint8)[None, :]
    return rgb


def _render(rgb, alpha=None, marcas=None, **ajustes):
    alto, ancho = rgb.shape[:2]
    alpha = np.ones((alto, ancho), np.float32) if alpha is None else alpha
    marcas = np.zeros((alto, ancho), np.uint8) if marcas is None else marcas
    return render(rgb, alpha, np.zeros((alto, ancho), bool), marcas, HalftoneSettings(**ajustes), NEGRO)


def test_s6_alfa_binario_y_rgb_cero_sin_tinta():
    salida = _render(_degradado())
    assert salida.dtype == np.uint8 and salida.shape == (64, 256, 4)
    assert set(np.unique(salida[..., 3])) <= {0, 255}
    assert (salida[salida[..., 3] == 0][:, :3] == 0).all()


def test_el_degradado_tiene_mas_tinta_lejos_del_color_de_la_camiseta():
    salida = _render(_degradado(), descartar=0, bordes_limpios_px=0)
    tinta = (salida[..., 3] > 0).mean(axis=0)
    assert tinta[:10].mean() < 0.06 and tinta[-10:].mean() > 0.94
    assert tinta[100:130].mean() < tinta[150:180].mean()


def test_cobertura_uno_siempre_y_cero_nunca():
    umbral = np.array([[0, 65535, 30000]], np.uint16)
    rgb = np.full((1, 3, 3), 200, np.uint8)
    llena = compose_output(rgb, np.ones((1, 3), np.float32), umbral, NEGRO, 0.0)
    vacia = compose_output(rgb, np.zeros((1, 3), np.float32), umbral, NEGRO, 0.0)
    assert (llena[..., 3] == 255).all() and (vacia[..., 3] == 0).all()


def test_s8_proteger_sale_solido_con_el_color_original():
    rgb = np.full((20, 20, 3), 30, np.uint8)
    marcas = np.zeros((20, 20), np.uint8)
    marcas[5:10, 5:10] = PROTEGER
    salida = _render(rgb, marcas=marcas)
    assert (salida[5:10, 5:10, 3] == 255).all()
    assert (salida[5:10, 5:10, :3] == 30).all()


def test_borrar_y_limpieza_quitan_la_tinta():
    rgb = np.full((10, 10, 3), 255, np.uint8)
    marcas = np.zeros((10, 10), np.uint8)
    marcas[:, :5] = BORRAR
    salida = _render(rgb, marcas=marcas)
    assert (salida[:, :5, 3] == 0).all() and (salida[:, 5:, 3] == 255).all()


def test_modos_de_semitransparencia():
    alfa = np.full((4, 4), 0.4, np.float32)
    cero = np.zeros((4, 4), bool)
    marcas = np.zeros((4, 4), np.uint8)
    np.testing.assert_allclose(visible_alpha(alfa, cero, marcas, AlphaMode.TRAMAR), 0.4)
    assert (visible_alpha(alfa, cero, marcas, AlphaMode.CORTAR) == 0).all()
    rgb = np.full((4, 4, 3), 255, np.uint8)
    cov = coverage_map(rgb, np.full((4, 4), 0.4, np.float32), marcas, HalftoneSettings(), NEGRO)
    np.testing.assert_allclose(cov, 0.4)
