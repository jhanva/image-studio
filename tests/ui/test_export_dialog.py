from image_studio.core.export import ExportSettings, Fondo
from image_studio.ui.export_dialog import ExportDialog


def test_valores_iniciales_de_ida_y_vuelta(qtbot):
    ajustes = ExportSettings(formato="webp", fondo=Fondo.COLOR, color=(10, 20, 30), recortar=True, margen_px=40, dpi=300)
    dialogo = ExportDialog(ajustes)
    qtbot.addWidget(dialogo)
    assert dialogo.ajustes() == ajustes


def test_cambiar_campos(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    dialogo.combo_formato.setCurrentText("jpg")
    dialogo.combo_fondo.setCurrentText("blanco")
    dialogo.check_recortar.setChecked(True)
    dialogo.spin_margen.setValue(25)
    dialogo.spin_dpi.setValue(150)
    assert dialogo.ajustes() == ExportSettings(formato="jpg", fondo=Fondo.BLANCO, recortar=True, margen_px=25, dpi=150)


def test_margen_solo_con_recorte(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert not dialogo.spin_margen.isEnabled()
    dialogo.check_recortar.setChecked(True)
    assert dialogo.spin_margen.isEnabled()


def test_dpi_cero_es_sin_cambio(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    dialogo.spin_dpi.setValue(0)
    assert dialogo.ajustes().dpi is None


def test_aviso_jpg_transparente(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert dialogo.aviso.isHidden()
    dialogo.combo_formato.setCurrentText("jpg")
    assert not dialogo.aviso.isHidden()


def test_color_solo_con_fondo_de_color(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert not dialogo.boton_color.isEnabled()
    dialogo.combo_fondo.setCurrentText("color")
    dialogo.set_color((1, 2, 3))
    assert dialogo.boton_color.isEnabled()
    assert dialogo.ajustes().color == (1, 2, 3)
