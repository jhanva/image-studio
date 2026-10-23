import numpy as np
import pytest

from image_studio.core.metrics import iou, mse, sad

UNOS = np.ones((10, 10), np.float32)
CEROS = np.zeros((10, 10), np.float32)


def test_iou():
    assert iou(UNOS, UNOS) == 1.0
    assert iou(UNOS, CEROS) == 0.0
    assert iou(CEROS, CEROS) == 1.0


def test_sad_en_miles():
    assert sad(UNOS, CEROS) == pytest.approx(0.1)


def test_mse():
    assert mse(UNOS * 0.5, CEROS) == pytest.approx(0.25)


def test_formas_distintas():
    with pytest.raises(ValueError):
        iou(UNOS, np.ones((5, 5), np.float32))
