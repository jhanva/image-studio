from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from image_studio.core.brush import Modo
from image_studio.core.export import ExportSettings
from image_studio.core.image_io import ImageDoc
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.session import EditSession, Pincel


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


def _doc(n: int = 200) -> ImageDoc:
    return ImageDoc(Path("x.png"), np.full((n, n, 3), 128, np.uint8), None, None, None)


def _resultado(doc: ImageDoc) -> RemovalResult:
    alfa = np.zeros(doc.rgb.shape[:2], np.float32)
    alfa[50:150, 50:150] = 1.0
    return RemovalResult(doc.rgb.copy(), alfa, None, False, "", {})


def test_sin_alfa_empieza_opaca():
    sesion = EditSession(_doc())
    assert (sesion.alpha == 1.0).all()
    assert not sesion.history.puede_deshacer


def test_aplicar_resultado_se_puede_deshacer():
    doc = _doc()
    resultado = _resultado(doc)
    sesion = EditSession(doc)
    assert sesion.apply_result(resultado) == (0, 0, 200, 200)
    assert np.array_equal(sesion.alpha, resultado.alpha) and sesion.rgb is resultado.rgb
    sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_trazo_borrar_y_deshacer():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.BORRAR, radio=10, dureza=1.0)
    assert sesion.begin_stroke(50, 100) == (40, 90, 61, 111)
    sesion.move_stroke(150, 100)
    sesion.end_stroke()
    assert sesion.alpha[100, 100] == 0.0 and sesion.alpha[0, 0] == 1.0
    assert sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_trazo_conservar():
    doc = _doc()
    sesion = EditSession(doc)
    sesion.apply_result(_resultado(doc))
    sesion.pincel = Pincel(Modo.CONSERVAR, radio=5, dureza=1.0)
    sesion.begin_stroke(10, 10)
    sesion.end_stroke()
    assert sesion.alpha[10, 10] == 1.0


def test_refinar_queda_pendiente_hasta_el_matting():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.REFINAR, radio=5, dureza=1.0)
    sesion.begin_stroke(100, 100)
    sesion.move_stroke(120, 100)
    sesion.end_stroke()
    assert sesion.refinado_pendiente and (sesion.alpha == 1.0).all()
    assert sesion.refine_pending(MatterFijo()) is not None
    assert not sesion.refinado_pendiente
    assert sesion.alpha[100, 110] == pytest.approx(0.42)
    sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_cancelar_refinado():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.REFINAR, radio=5, dureza=1.0)
    sesion.begin_stroke(100, 100)
    sesion.end_stroke()
    sesion.cancel_refine()
    assert not sesion.refinado_pendiente and not sesion.trazo_abierto
    sesion.undo()


def test_no_deshace_con_trazo_abierto():
    sesion = EditSession(_doc())
    sesion.begin_stroke(10, 10)
    with pytest.raises(RuntimeError):
        sesion.undo()


def test_mover_sin_trazo_no_hace_nada():
    assert EditSession(_doc()).move_stroke(1, 1) is None


def test_exporta_png(tmp_path):
    doc = _doc()
    sesion = EditSession(doc)
    sesion.apply_result(_resultado(doc))
    ruta = sesion.export(tmp_path / "a.png", ExportSettings(), limpiar_color=False)
    with Image.open(ruta) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[100, 100] == 255


def test_v8_cincuenta_trazos_en_6000x4000():
    doc = ImageDoc(Path("g.png"), np.zeros((4000, 6000, 3), np.uint8), None, None, None)
    sesion = EditSession(doc)
    sesion.pincel = Pincel(Modo.BORRAR, radio=30, dureza=0.8)
    rng = np.random.default_rng(0)
    for _ in range(50):
        x, y = rng.uniform(100, 5600), rng.uniform(100, 3800)
        sesion.begin_stroke(x, y)
        sesion.move_stroke(x + 300, y + 50)
        sesion.end_stroke()
    assert (sesion.alpha < 1.0).any()
    assert sesion.history.bytes_usados < 1 << 30
    for _ in range(50):
        sesion.undo()
    assert (sesion.alpha == 1.0).all()
