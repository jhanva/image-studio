import numpy as np
import pytest

from image_studio.core.halftone.screen import (
    UMBRAL_MAX,
    periodo_celdas,
    screen_for,
    snap_screen,
    threshold_field,
)
from image_studio.core.halftone.settings import HalftoneSettings, Pattern


@pytest.mark.parametrize("patron", list(Pattern))
@pytest.mark.parametrize("rejilla", [True, False])
def test_s3_fraccion_entintada_igual_a_la_cobertura(patron, rejilla):
    ajustes = HalftoneSettings(patron=patron, ajustar_rejilla=rejilla)
    umbral = threshold_field((7, 11, 7 + 512, 11 + 512), ajustes)
    for cobertura in np.arange(0.1, 0.91, 0.1):
        fraccion = np.mean(cobertura * UMBRAL_MAX > umbral)
        assert abs(fraccion - cobertura) < 0.02, (patron, cobertura, fraccion)


@pytest.mark.parametrize("patron", list(Pattern))
def test_s9_periodicidad_con_ajuste_a_la_rejilla(patron):
    ajustes = HalftoneSettings(patron=patron, lpi=35, angulo=22.5)
    pantalla = screen_for(ajustes)
    k = periodo_celdas(patron)
    dx, dy = k * int(pantalla.bx), k * int(pantalla.by)
    base = threshold_field((50, 50, 250, 250), ajustes)
    movido = threshold_field((50 + dx, 50 + dy, 250 + dx, 250 + dy), ajustes)
    np.testing.assert_array_equal(base, movido)


def test_snap_ajusta_a_vector_entero_cercano():
    pantalla = snap_screen(300 / 35, 22.5)
    assert (pantalla.bx, pantalla.by) == (8.0, 3.0)
    assert round(pantalla.lpi, 1) == 35.1 and round(pantalla.angulo, 1) == 20.6


def test_el_campo_es_el_mismo_por_rectangulos():
    ajustes = HalftoneSettings(angulo=45, lpi=30)
    todo = threshold_field((0, 0, 300, 200), ajustes)
    np.testing.assert_array_equal(todo[40:120, 90:250], threshold_field((90, 40, 250, 120), ajustes))
    sin = HalftoneSettings(angulo=45, lpi=30, ajustar_rejilla=False)
    np.testing.assert_array_equal(
        threshold_field((0, 0, 300, 200), sin)[40:120, 90:250], threshold_field((90, 40, 250, 120), sin)
    )
