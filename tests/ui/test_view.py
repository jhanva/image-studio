import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer


def _evento(tipo, x, y, boton, botones):
    punto = QPointF(x, y)
    return QMouseEvent(tipo, punto, punto, boton, botones, Qt.KeyboardModifier.NoModifier)


@pytest.fixture
def vista(qtbot):
    vista = CanvasView()
    qtbot.addWidget(vista)
    vista.resize(400, 300)
    vista.show()
    rgb = np.zeros((100, 200, 3), np.uint8)
    vista._buffers = (RgbaBuffer(rgb, np.ones((100, 200), np.float32)), RgbBuffer(rgb))
    vista.set_images(vista._buffers[0].imagen, vista._buffers[1].imagen)
    return vista


def test_ajustar_encaja_la_imagen(vista):
    assert 1.5 < vista.escala < 2.1


def test_zoom_respeta_limites(vista):
    vista.zoom(1000)
    assert vista.escala == pytest.approx(CanvasView.ESCALA_MAX)
    vista.zoom(1e-6)
    assert vista.escala == pytest.approx(CanvasView.ESCALA_MIN)


def test_trazo_emite_coordenadas_de_la_imagen(vista):
    eventos = []
    vista.trazo_inicio.connect(lambda p: eventos.append(("inicio", p)))
    vista.trazo_mueve.connect(lambda p: eventos.append(("mueve", p)))
    vista.trazo_fin.connect(lambda: eventos.append(("fin", None)))
    vista.pintura_habilitada = True
    centro = vista.viewport().rect().center()
    izq = Qt.MouseButton.LeftButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, centro.x(), centro.y(), izq, izq))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseMove, centro.x() + 20, centro.y(), Qt.MouseButton.NoButton, izq))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonRelease, centro.x() + 20, centro.y(), izq, Qt.MouseButton.NoButton))
    assert [e[0] for e in eventos] == ["inicio", "mueve", "fin"]
    inicio = eventos[0][1]
    assert abs(inicio.x() - 100) < 2 and abs(inicio.y() - 50) < 2
    assert eventos[1][1].x() > inicio.x()


def test_sin_pintura_habilitada_no_emite(vista):
    eventos = []
    vista.trazo_inicio.connect(eventos.append)
    izq = Qt.MouseButton.LeftButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, 200, 150, izq, izq))
    assert eventos == []


def test_boton_central_desplaza(vista):
    vista.zoom(4)
    barra = vista.horizontalScrollBar()
    barra.setValue(barra.maximum() // 2)
    antes = barra.value()
    medio = Qt.MouseButton.MiddleButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, 200, 150, medio, medio))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseMove, 150, 150, Qt.MouseButton.NoButton, medio))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonRelease, 150, 150, medio, Qt.MouseButton.NoButton))
    assert barra.value() == antes + 50


def test_vista_previa_de_refinar(vista):
    vista.iniciar_vista_refinar(10, QPointF(10, 10))
    vista.agregar_punto_refinar(QPointF(50, 10))
    assert not vista.ruta_refinar.isEmpty()
    vista.limpiar_vista_refinar()
    assert vista.ruta_refinar.isEmpty()
