import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.ui.main_window import MainWindow


class RemovedorFijo:
    def run(self, doc, ajustes, usar_alfa_existente=False):
        alfa = np.zeros(doc.rgb.shape[:2], np.float32)
        alfa[20:80, 20:80] = 1.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.01})


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


@pytest.fixture
def ventana(qtbot):
    ventana = MainWindow(crear_removedor=lambda modelo, dispositivo, progreso: RemovedorFijo(), matter=MatterFijo())
    qtbot.addWidget(ventana)
    ventana.resize(800, 600)
    ventana.show()
    return ventana


@pytest.fixture
def abierta(ventana, escribir_png, tmp_path):
    assert ventana.abrir(escribir_png(tmp_path / "foto.png", ancho=100, alto=100))
    return ventana


def _trazo(ventana, desde, hasta):
    ventana._trazo_inicio(QPointF(*desde))
    ventana._trazo_mueve(QPointF(*hasta))
    ventana._trazo_fin()


def test_estado_inicial(ventana):
    assert ventana.sesion is None
    assert not ventana.accion_quitar.isEnabled() and ventana.accion_abrir.isEnabled()


def test_abrir_imagen(abierta):
    assert abierta.sesion.doc.size == (100, 100)
    assert "foto.png" in abierta.windowTitle()
    assert abierta.accion_quitar.isEnabled()


def test_archivo_corrupto_muestra_error(ventana, tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"x")
    assert not ventana.abrir(ruta)
    assert "No se pudo leer" in ventana.statusBar().currentMessage()
    assert ventana.sesion is None


def test_quitar_fondo_en_segundo_plano(abierta, qtbot):
    abierta.quitar_fondo()
    assert abierta.ocupado
    qtbot.waitUntil(lambda: not abierta.ocupado)
    assert abierta.sesion.alpha[50, 50] == 1.0 and abierta.sesion.alpha[0, 0] == 0.0
    assert "Fondo quitado" in abierta.statusBar().currentMessage()


def test_sin_herramienta_no_pinta(abierta):
    _trazo(abierta, (50, 50), (60, 50))
    assert (abierta.sesion.alpha == 1.0).all()


def test_borrar_y_deshacer(abierta):
    abierta.accion_borrar.trigger()
    abierta.spin_radio.setValue(5)
    abierta.spin_dureza.setValue(100)
    _trazo(abierta, (50, 50), (60, 50))
    assert abierta.sesion.alpha[50, 55] == 0.0
    assert abierta.accion_deshacer.isEnabled()
    abierta.deshacer()
    assert (abierta.sesion.alpha == 1.0).all()
    abierta.rehacer()
    assert abierta.sesion.alpha[50, 55] == 0.0


def test_refinar_corre_en_segundo_plano(abierta, qtbot):
    abierta.accion_refinar.trigger()
    abierta.spin_radio.setValue(5)
    _trazo(abierta, (50, 50), (60, 50))
    qtbot.waitUntil(lambda: not abierta.ocupado)
    assert abierta.sesion.alpha[50, 55] == pytest.approx(0.42)
    assert abierta.lienzo.ruta_refinar.isEmpty()
    abierta.deshacer()
    assert (abierta.sesion.alpha == 1.0).all()


def test_guardar_png(abierta, qtbot, tmp_path):
    abierta.quitar_fondo()
    qtbot.waitUntil(lambda: not abierta.ocupado)
    destino = abierta.guardar_en(tmp_path / "salida.png")
    with Image.open(destino) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[50, 50] == 255


def test_pegar_desde_portapapeles(ventana):
    imagen = QImage(30, 20, QImage.Format.Format_RGBA8888)
    imagen.fill(QColor(10, 20, 30, 255))
    QApplication.clipboard().setImage(imagen)
    ventana.pegar()
    assert ventana.sesion.doc.size == (30, 20)


def test_ver_original(abierta):
    abierta.accion_antes.trigger()
    assert abierta.lienzo.capa.mostrando_antes
