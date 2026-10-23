from PySide6.QtWidgets import QDialogButtonBox

from image_studio.pipeline.settings import PRESETS, PipelineSettings
from image_studio.ui.preset_dialog import PresetDialog


def _ok(dialogo):
    return dialogo.botones.button(QDialogButtonBox.StandardButton.Ok)


def test_parte_del_preset_base(qtbot):
    base = PipelineSettings(modelo="isnet", matting=False, banda_px=7, desplazamiento_px=-2, suavizado_px=1.5)
    dialogo = PresetDialog(base, set(PRESETS))
    qtbot.addWidget(dialogo)
    dialogo.edit_nombre.setText("Tazas")
    assert dialogo.valor() == ("Tazas", base)


def test_nombre_vacio_o_reservado_no_se_acepta(qtbot):
    dialogo = PresetDialog(PipelineSettings(), set(PRESETS))
    qtbot.addWidget(dialogo)
    assert not _ok(dialogo).isEnabled()
    dialogo.edit_nombre.setText("producto")
    assert not _ok(dialogo).isEnabled()
    assert "incluido" in dialogo.error.text()
    dialogo.edit_nombre.setText("Tazas")
    assert _ok(dialogo).isEnabled() and dialogo.error.text() == ""


def test_cambiar_campos(qtbot):
    dialogo = PresetDialog(PipelineSettings(), set(PRESETS))
    qtbot.addWidget(dialogo)
    dialogo.edit_nombre.setText(" Gorras ")
    dialogo.combo_modelo.setCurrentText("isnet")
    dialogo.check_matting.setChecked(False)
    dialogo.check_limpieza.setChecked(False)
    dialogo.spin_banda.setValue(4)
    dialogo.spin_desplazamiento.setValue(3)
    dialogo.spin_suavizado.setValue(0.5)
    assert dialogo.valor() == (
        "Gorras",
        PipelineSettings(modelo="isnet", matting=False, limpieza_color=False, banda_px=4, desplazamiento_px=3, suavizado_px=0.5),
    )
