import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from image_studio.core.halftone.render import BORRAR, PROTEGER
from image_studio.core.halftone.settings import KnockoutMode, Pattern
from image_studio.pipeline.halftone_presets import HalftonePresetStore
from image_studio.tools.halftone.panel import HalftoneTool


def _diseno(ruta, ancho=480, alto=320):
    """Fondo negro con un degradado rojo y un bloque blanco."""
    rgb = np.zeros((alto, ancho, 3), np.uint8)
    rgb[40:280, 40:440, 0] = np.linspace(0, 255, 400).astype(np.uint8)[None, :]
    rgb[120:200, 360:440] = 255
    Image.fromarray(rgb).save(ruta)
    return ruta


@pytest.fixture
def herramienta(qtbot):
    tool = HalftoneTool(HalftonePresetStore())
    qtbot.addWidget(tool)
    tool.resize(1100, 700)
    tool.show()
    return tool


@pytest.fixture
def abierta(herramienta, tmp_path, qtbot):
    assert herramienta.abrir(_diseno(tmp_path / "diseño ñ.png"))
    qtbot.waitUntil(lambda: herramienta.vista_al_dia, timeout=5000)
    return herramienta


def test_estado_inicial(herramienta):
    assert herramienta.id == "semitonos" and herramienta.nombre == "Semitonos"
    assert herramienta.sesion is None
    assert not herramienta.accion_exportar.isEnabled()
    assert herramienta.combo_preset.currentText() == "Camiseta negra"
    assert "35.1 LPI a 20.6°" in herramienta.etiqueta_trama.text()


def test_abrir_muestra_la_vista_previa(abierta):
    datos = abierta._datos
    assert datos.shape == (320, 480, 4)
    assert datos[0, 0, 3] == 0  # el negro de la camiseta se elimina
    assert datos[160, 400, 3] == 255  # el blanco queda sólido
    assert "Vista previa actualizada" in abierta.ultimo_mensaje


def test_mover_un_control_recalcula(abierta, qtbot):
    generacion = abierta.generacion_completa
    antes = abierta._datos.copy()
    abierta.combo_patron.setCurrentIndex(abierta.combo_patron.findData(Pattern.LINEA.value))
    qtbot.waitUntil(lambda: abierta.vista_al_dia and abierta.generacion_completa != generacion, timeout=5000)
    assert abierta.sesion.ajustes.patron is Pattern.LINEA
    assert not np.array_equal(antes, abierta._datos)


def test_varios_cambios_seguidos_terminan_en_el_ultimo(abierta, qtbot):
    for lpi in (20, 30, 40, 50):
        abierta.control_lpi.setValue(lpi)
    qtbot.waitUntil(lambda: abierta.vista_al_dia, timeout=5000)
    assert abierta.sesion.ajustes.lpi == 50
    _, esperado = abierta.sesion.render()
    np.testing.assert_array_equal(abierta._datos, esperado)


def test_pintar_proteger_y_deshacer(abierta, qtbot):
    abierta.accion_proteger.trigger()
    assert abierta.lienzo.pintura_habilitada
    abierta.casilla_pincel.setValue(0.1)
    abierta._trazo_inicio(QPointF(120, 160))
    abierta._trazo_mueve(QPointF(160, 160))
    abierta._trazo_fin()
    assert abierta.sesion.marcas[160, 140] == PROTEGER
    qtbot.waitUntil(lambda: abierta.vista_al_dia, timeout=5000)
    assert abierta._datos[160, 140, 3] == 255
    assert abierta.accion_deshacer.isEnabled()
    abierta.deshacer()
    assert abierta.sesion.marcas[160, 140] == 0
    abierta.accion_borrar.trigger()
    abierta._trazo_inicio(QPointF(400, 160))
    abierta._trazo_fin()
    assert abierta.sesion.marcas[160, 400] == BORRAR
    abierta.limpiar_borradores()
    assert not abierta.sesion.marcas.any()


def test_cuentagotas_toma_el_color_a_eliminar_y_los_colores_a_borrar(abierta):
    abierta.activar_cuentagotas("knockout")
    assert abierta.lienzo.pintura_habilitada
    abierta._trazo_inicio(QPointF(400, 160))
    assert abierta.combo_knockout.currentData() == KnockoutMode.ELEGIDO
    assert abierta.ajustes_actuales().color_elegido == (255, 255, 255)
    abierta.activar_cuentagotas("borrar")
    abierta._trazo_inicio(QPointF(5, 5))
    assert abierta.ajustes_actuales().colores_borrar == ((0, 0, 0),)
    assert not abierta.lienzo.pintura_habilitada


def test_vista_sobre_camiseta(abierta):
    abierta.fijar_color_camiseta((10, 120, 30))
    assert abierta.lienzo._fondo == QColor(10, 120, 30)
    abierta.accion_camiseta.setChecked(False)
    abierta._actualizar_fondo()
    assert abierta.lienzo._fondo is None


def test_cambiar_ancho_remuestrea(abierta, qtbot):
    abierta.casilla_ancho.setValue(2.0)
    assert abierta.sesion.forma == (400, 600)
    assert abierta._datos.shape[:2] == (400, 600)
    assert abierta.etiqueta_pixeles.text() == "600 x 400"
    qtbot.waitUntil(lambda: abierta.vista_al_dia, timeout=5000)


def test_presets_propios(abierta):
    abierta.control_lpi.setValue(45)
    abierta.guardar_preset("Mío")
    assert abierta.combo_preset.currentText() == "Mío"
    abierta.aplicar_preset("Camiseta blanca")
    assert abierta.combo_knockout.currentData() == KnockoutMode.BLANCO
    assert abierta.control_lpi.value() == 35
    abierta.aplicar_preset("Mío")
    assert abierta.control_lpi.value() == 45
    abierta.borrar_preset("Mío")
    assert abierta.combo_preset.findText("Mío") < 0


def test_exportar(abierta, tmp_path, qtbot):
    qtbot.waitUntil(lambda: abierta.vista_al_dia, timeout=5000)
    ruta = abierta.exportar_en(tmp_path / "salida.png")
    with Image.open(ruta) as imagen:
        assert imagen.mode == "RGBA" and round(imagen.info["dpi"][0]) == 300
        np.testing.assert_array_equal(np.asarray(imagen), abierta._datos)


def test_exportar_sin_tinta_pide_confirmacion(herramienta, tmp_path, qtbot):
    Image.fromarray(np.zeros((50, 50, 3), np.uint8)).save(tmp_path / "negro.png")
    herramienta.abrir(tmp_path / "negro.png")
    assert herramienta.exportar_en(tmp_path / "x.png", confirmar_sin_tinta=lambda: False) is None
    assert not (tmp_path / "x.png").exists()
    assert herramienta.exportar_en(tmp_path / "x.png", confirmar_sin_tinta=lambda: True).exists()


def test_archivo_invalido(herramienta, tmp_path):
    (tmp_path / "roto.png").write_bytes(b"no es imagen")
    assert not herramienta.abrir(tmp_path / "roto.png")
    assert herramienta.sesion is None
