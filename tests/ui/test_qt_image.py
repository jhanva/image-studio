import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage

from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer, qimage_to_arrays


def test_buffer_rgba_refleja_cambios_sin_copiar(qapp):
    rgb = np.zeros((4, 6, 3), np.uint8)
    rgb[...] = (200, 10, 20)
    alfa = np.ones((4, 6), np.float32)
    buffer = RgbaBuffer(rgb, alfa)
    assert buffer.imagen.pixelColor(1, 1) == QColor(200, 10, 20, 255)
    alfa[1, 1] = 0.0
    buffer.update(rgb, alfa, (0, 0, 2, 2))
    assert buffer.imagen.pixelColor(1, 1).alpha() == 0
    assert buffer.imagen.pixelColor(5, 3).alpha() == 255


def test_buffer_rgb(qapp):
    rgb = np.zeros((3, 5, 3), np.uint8)
    rgb[2, 4] = (1, 2, 3)
    assert RgbBuffer(rgb).imagen.pixelColor(4, 2) == QColor(1, 2, 3)


def test_qimage_a_arreglos_con_alfa(qapp):
    imagen = QImage(5, 3, QImage.Format.Format_ARGB32)
    imagen.fill(QColor(10, 20, 30, 128))
    rgb, alfa = qimage_to_arrays(imagen)
    assert rgb.shape == (3, 5, 3) and tuple(rgb[0, 0]) == (10, 20, 30)
    assert alfa.dtype == np.float32 and alfa[0, 0] == pytest.approx(128 / 255)


def test_qimage_opaca_no_tiene_alfa(qapp):
    imagen = QImage(5, 3, QImage.Format.Format_RGB32)
    imagen.fill(QColor(1, 2, 3))
    rgb, alfa = qimage_to_arrays(imagen)
    assert alfa is None and tuple(rgb[2, 4]) == (1, 2, 3)
