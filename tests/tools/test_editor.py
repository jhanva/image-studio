import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.settings import PipelineSettings
from image_studio.tools.background_removal.editor import EditorTool


class RemovedorFijo:
    def __init__(self):
        self.ajustes = []

    def run(self, doc, ajustes, usar_alfa_existente=False):
        self.ajustes.append(ajustes)
        alfa = np.zeros(doc.rgb.shape[:2], np.float32)
        alfa[20:80, 20:80] = 1.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.01})


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


@pytest.fixture
def removedor():
    return RemovedorFijo()


@pytest.fixture
def editor(qtbot, removedor):
    cache = RemoverCache(lambda modelo, dispositivo, progreso: removedor)
    editor = EditorTool(cache, PresetStore(), matter=MatterFijo())
    qtbot.addWidget(editor)
    editor.resize(800, 600)
    editor.show()
    return editor


@pytest.fixture
def abierto(editor, escribir_png, tmp_path):
    assert editor.abrir(escribir_png(tmp_path / "foto.png", ancho=100, alto=100))
    return editor


def _trazo(editor, desde, hasta):
    editor._trazo_inicio(QPointF(*desde))
    editor._trazo_mueve(QPointF(*hasta))
    editor._trazo_fin()


def test_estado_inicial(editor):
    assert editor.id == "editor" and editor.sesion is None
    assert not editor.accion_quitar.isEnabled() and editor.accion_abrir.isEnabled()


def test_abrir_imagen(abierto):
    assert abierto.sesion.doc.size == (100, 100)
    assert "foto.png" in abierto.ultimo_mensaje
    assert abierto.accion_quitar.isEnabled()


def test_archivo_corrupto_muestra_error(editor, tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"x")
    assert not editor.abrir(ruta)
    assert "No se pudo leer" in editor.ultimo_mensaje
    assert editor.sesion is None


def test_quitar_fondo_en_segundo_plano(abierto, qtbot):
    abierto.quitar_fondo()
    assert abierto.ocupado
    qtbot.waitUntil(lambda: not abierto.ocupado)
    assert abierto.sesion.alpha[50, 50] == 1.0 and abierto.sesion.alpha[0, 0] == 0.0
    assert "Fondo quitado" in abierto.ultimo_mensaje


def test_usa_presets_propios(editor, escribir_png, tmp_path, removedor, qtbot):
    PresetStore().guardar("Tazas", PipelineSettings(matting=False, banda_px=4))
    editor.recargar_presets("Tazas")
    assert editor.combo_preset.currentText() == "Tazas"
    editor.abrir(escribir_png(tmp_path / "taza.png", ancho=100, alto=100))
    editor.quitar_fondo()
    qtbot.waitUntil(lambda: not editor.ocupado)
    assert removedor.ajustes[-1] == PipelineSettings(matting=False, banda_px=4)


def test_sin_herramienta_no_pinta(abierto):
    _trazo(abierto, (50, 50), (60, 50))
    assert (abierto.sesion.alpha == 1.0).all()


def test_borrar_y_deshacer(abierto):
    abierto.accion_borrar.trigger()
    abierto.spin_radio.setValue(5)
    abierto.spin_dureza.setValue(100)
    _trazo(abierto, (50, 50), (60, 50))
    assert abierto.sesion.alpha[50, 55] == 0.0
    assert abierto.accion_deshacer.isEnabled()
    abierto.deshacer()
    assert (abierto.sesion.alpha == 1.0).all()
    abierto.rehacer()
    assert abierto.sesion.alpha[50, 55] == 0.0


def test_refinar_corre_en_segundo_plano(abierto, qtbot):
    abierto.accion_refinar.trigger()
    abierto.spin_radio.setValue(5)
    _trazo(abierto, (50, 50), (60, 50))
    qtbot.waitUntil(lambda: not abierto.ocupado)
    assert abierto.sesion.alpha[50, 55] == pytest.approx(0.42)
    assert abierto.lienzo.ruta_refinar.isEmpty()
    abierto.deshacer()
    assert (abierto.sesion.alpha == 1.0).all()


def test_guardar_png(abierto, qtbot, tmp_path):
    abierto.quitar_fondo()
    qtbot.waitUntil(lambda: not abierto.ocupado)
    destino = abierto.guardar_en(tmp_path / "salida.png")
    with Image.open(destino) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[50, 50] == 255


def test_pegar_desde_portapapeles(editor):
    imagen = QImage(30, 20, QImage.Format.Format_RGBA8888)
    imagen.fill(QColor(10, 20, 30, 255))
    QApplication.clipboard().setImage(imagen)
    editor.pegar()
    assert editor.sesion.doc.size == (30, 20)


def test_ver_original(abierto):
    abierto.accion_antes.trigger()
    assert abierto.lienzo.capa.mostrando_antes
