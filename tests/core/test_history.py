import numpy as np
import pytest

from image_studio.core.history import MaskHistory

BYTES_TILE = 256 * 256 * 4


def _paso(historial, mascara, rect, valor):
    historial.begin()
    historial.touch(*rect)
    x0, y0, x1, y1 = rect
    mascara[y0:y1, x0:x1] = valor
    historial.end()


def test_deshacer_y_rehacer():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (10, 10, 20, 20), 1.0)
    assert historial.undo() == [(0, 0, 256, 256)]
    assert (mascara == 0).all()
    historial.redo()
    assert mascara[15, 15] == 1.0


def test_paso_nuevo_borra_rehacer():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (0, 0, 10, 10), 1.0)
    historial.undo()
    _paso(historial, mascara, (0, 0, 10, 10), 0.5)
    assert not historial.puede_rehacer


def test_tocar_dos_veces_conserva_el_estado_original():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    historial.begin()
    historial.touch(0, 0, 10, 10)
    mascara[0:10, 0:10] = 0.5
    historial.touch(0, 0, 10, 10)
    mascara[0:10, 0:10] = 1.0
    historial.end()
    historial.undo()
    assert (mascara == 0).all()


def test_paso_vacio_no_se_guarda():
    historial = MaskHistory(np.zeros((10, 10), np.float32))
    historial.begin()
    historial.end()
    assert not historial.puede_deshacer


def test_limite_de_pasos():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara, max_pasos=2)
    for valor in (1.0, 2.0, 3.0):
        _paso(historial, mascara, (0, 0, 1, 1), valor)
    historial.undo()
    historial.undo()
    assert mascara[0, 0] == 1.0
    assert not historial.puede_deshacer


def test_limite_de_memoria():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara, max_bytes=2 * BYTES_TILE)
    for valor in (1.0, 2.0, 3.0):
        _paso(historial, mascara, (0, 0, 1, 1), valor)
    assert historial.bytes_usados == 2 * BYTES_TILE


def test_tiles_del_borde():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (250, 250, 300, 300), 1.0)
    assert sorted(historial.undo()) == [
        (0, 0, 256, 256),
        (0, 256, 256, 300),
        (256, 0, 300, 256),
        (256, 256, 300, 300),
    ]


def test_errores_de_uso():
    historial = MaskHistory(np.zeros((10, 10), np.float32))
    with pytest.raises(RuntimeError):
        historial.touch(0, 0, 1, 1)
    with pytest.raises(RuntimeError):
        historial.end()
    historial.begin()
    with pytest.raises(RuntimeError):
        historial.begin()
