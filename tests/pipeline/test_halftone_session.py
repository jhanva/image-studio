from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from image_studio.core.halftone.render import BORRAR, PROTEGER
from image_studio.core.halftone.settings import HalftoneSettings
from image_studio.core.image_io import ImageDoc
from image_studio.pipeline.halftone_session import HalftoneSession, ModoBorrador


def _doc(ancho=300, alto=200, alpha=None):
    rgb = np.zeros((alto, ancho, 3), np.uint8)
    rgb[..., 0] = np.linspace(0, 255, ancho).astype(np.uint8)[None, :]
    rgb[..., 1] = 60
    return ImageDoc(Path("arte.png"), rgb, alpha, None, None)


def test_por_defecto_conserva_los_pixeles_a_300_dpi():
    sesion = HalftoneSession(_doc())
    assert sesion.forma == (200, 300) and sesion.ancho_pulgadas == 1.0
    assert sesion.rgb is sesion.doc.rgb


def test_cambiar_ancho_remuestrea_imagen_y_marcas_y_reinicia_historial():
    sesion = HalftoneSession(_doc())
    sesion.borrador.radio = 10
    sesion.begin_stroke(150, 100)
    sesion.end_stroke()
    assert sesion.history.puede_deshacer
    assert not sesion.set_ancho(2.0)
    assert sesion.forma == (400, 600)
    assert sesion.marcas[200, 300] == PROTEGER
    assert not sesion.history.puede_deshacer


def test_el_ancho_se_limita_a_60_mp_y_a_30_pulgadas():
    sesion = HalftoneSession(_doc())
    assert sesion.set_ancho(500)
    assert sesion.ancho_pulgadas == pytest.approx(sesion.ancho_maximo())
    assert sesion.ancho_maximo() <= 30
    angosta = HalftoneSession(_doc(ancho=100, alto=10000))
    assert angosta.ancho_maximo() * 300 * angosta.ancho_maximo() * 300 * 100 <= 60_000_000 * 1.01


def test_s7_la_exportacion_es_igual_a_la_vista_previa(tmp_path):
    sesion = HalftoneSession(_doc(), HalftoneSettings(patron="diamante", lpi=45))
    _, vista = sesion.render()
    ruta = sesion.export(tmp_path / "salida ñ.png")
    with Image.open(ruta) as imagen:
        assert imagen.mode == "RGBA"
        assert round(imagen.info["dpi"][0]) == 300
        np.testing.assert_array_equal(np.asarray(imagen), vista)
    assert set(np.unique(vista[..., 3])) <= {0, 255}


def test_un_rectangulo_coincide_con_la_imagen_completa():
    sesion = HalftoneSession(_doc(), HalftoneSettings(angulo=45))
    _, todo = sesion.render()
    rect, parte = sesion.render((40, 30, 170, 120))
    assert rect == (40, 30, 170, 120)
    np.testing.assert_array_equal(parte, todo[30:120, 40:170])
    assert sesion.render((400, 400, 500, 500)) is None


def test_s10_cambiar_solo_el_lpi_no_recalcula_las_etapas_anteriores():
    sesion = HalftoneSession(_doc())
    sesion.render()
    antes = dict(sesion.contadores)
    sesion.set_ajustes(HalftoneSettings(lpi=45))
    sesion.render()
    for etapa in ("imagen", "limpieza", "visible", "cobertura"):
        assert sesion.contadores[etapa] == antes.get(etapa, 0), etapa
    assert sesion.contadores["umbral"] == antes["umbral"] + 1
    sesion.set_ajustes(HalftoneSettings(lpi=45, alcance=50))
    sesion.render()
    assert sesion.contadores["cobertura"] == antes["cobertura"] + 1
    assert sesion.contadores["limpieza"] == antes["limpieza"]


def test_un_resultado_de_generacion_vieja_se_descarta_y_no_queda_en_cache():
    sesion = HalftoneSession(_doc())
    vieja = sesion.nueva_generacion()
    sesion.nueva_generacion()
    assert sesion.render(generacion=vieja) is None
    assert sesion.render(generacion=sesion.generacion) is not None


def test_borradores_y_s11_deshacer_50_trazos():
    sesion = HalftoneSession(_doc())
    original = sesion.marcas.copy()
    rng = np.random.default_rng(1)
    modos = list(ModoBorrador)
    for i in range(50):
        sesion.borrador.modo = modos[i % 3]
        sesion.borrador.radio = float(rng.integers(3, 20))
        x, y = rng.integers(0, 300), rng.integers(0, 200)
        sesion.begin_stroke(x, y)
        sesion.move_stroke(x + 30, y + 10)
        sesion.end_stroke()
    assert (sesion.marcas == BORRAR).any() and (sesion.marcas == PROTEGER).any()
    while sesion.history.puede_deshacer:
        sesion.undo()
    np.testing.assert_array_equal(sesion.marcas, original)


def test_borrar_quita_la_tinta_y_limpiar_todo_la_devuelve():
    doc = _doc()
    doc.rgb[...] = 255
    sesion = HalftoneSession(doc)
    sesion.borrador.modo = ModoBorrador.BORRAR
    sesion.borrador.radio = 20
    sesion.begin_stroke(100, 100)
    sesion.end_stroke()
    _, salida = sesion.render()
    assert salida[100, 100, 3] == 0 and salida[10, 10, 3] == 255
    sesion.clear_marks()
    _, salida = sesion.render()
    assert salida[100, 100, 3] == 255
    sesion.undo()
    assert sesion.marcas[100, 100] == BORRAR


def test_hay_tinta():
    doc = _doc()
    doc.rgb[...] = 0
    sesion = HalftoneSession(doc)
    _, salida = sesion.render()
    assert not HalftoneSession.hay_tinta(salida)


def test_alfa_original_y_fondo_detectado():
    alfa = np.ones((200, 300), np.float32)
    alfa[:, :20] = 0.0
    sesion = HalftoneSession(_doc(alpha=alfa), HalftoneSettings(quitar_fondo=True))
    _, salida = sesion.render()
    assert (salida[:, :20, 3] == 0).all()
    assert sesion.ultimo_fondo is not None


def test_vista_parcial_sin_cache_coincide_con_la_completa():
    doc = _doc()
    doc.rgb[90:110, :, :] = 255  # franja sólida para que bordes limpios actúe en el borde del rectángulo
    ajustes = HalftoneSettings(bordes_limpios_px=4, alcance=60)
    parcial = HalftoneSession(doc, ajustes)
    parcial.borrador.radio = 6
    parcial.begin_stroke(120, 60)
    parcial.end_stroke()
    rect, zona = parcial.render((100, 50, 200, 100))
    assert parcial.contadores["cobertura_parcial"] == 1 and parcial.contadores["cobertura"] == 0
    _, todo = parcial.render()
    np.testing.assert_array_equal(zona, todo[50:100, 100:200])
