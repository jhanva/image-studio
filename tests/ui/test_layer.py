import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsScene

from image_studio.ui.canvas.layer import ImageLayer
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer


def _render(escena: QGraphicsScene) -> QImage:
    destino = QImage(10, 10, QImage.Format.Format_ARGB32)
    destino.fill(QColor(255, 255, 255))
    pintor = QPainter(destino)
    escena.render(pintor, QRectF(0, 0, 10, 10), QRectF(0, 0, 10, 10))
    pintor.end()
    return destino


def _capa():
    rgb = np.zeros((10, 10, 3), np.uint8)
    rgb[...] = (255, 0, 0)
    alfa = np.zeros((10, 10), np.float32)
    alfa[:, 5:] = 1.0
    despues, antes = RgbaBuffer(rgb, alfa), RgbBuffer(rgb)
    capa = ImageLayer()
    capa.set_images(despues.imagen, antes.imagen)
    escena = QGraphicsScene()
    escena.addItem(capa)
    return capa, escena, (despues, antes)


def test_sin_imagen_no_ocupa_espacio(qapp):
    assert ImageLayer().boundingRect().isEmpty()


def test_dibuja_el_recorte_con_transparencia(qapp):
    capa, escena, _buffers = _capa()
    assert capa.boundingRect() == QRectF(0, 0, 10, 10)
    imagen = _render(escena)
    assert imagen.pixelColor(2, 5) == QColor(255, 255, 255)
    assert imagen.pixelColor(8, 5) == QColor(255, 0, 0)


def test_antes_muestra_el_original(qapp):
    capa, escena, _buffers = _capa()
    capa.set_show_before(True)
    assert capa.mostrando_antes
    assert _render(escena).pixelColor(2, 5) == QColor(255, 0, 0)
