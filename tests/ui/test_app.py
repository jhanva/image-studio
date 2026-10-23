from PySide6.QtGui import QPalette

from image_studio.ui.app import FONDO_VENTANA, aplicar_tema, crear_ventana


def test_tema_oscuro(qapp):
    aplicar_tema(qapp)
    assert qapp.style().name().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window) == FONDO_VENTANA


def test_crear_ventana_abre_la_imagen_en_el_editor(qtbot, escribir_png, tmp_path):
    ventana = crear_ventana([str(escribir_png(tmp_path / "a.png"))])
    qtbot.addWidget(ventana)
    assert ventana.actual().id == "editor"
    assert ventana.herramienta("editor").sesion is not None


def test_crear_ventana_sin_imagen(qtbot):
    ventana = crear_ventana([])
    qtbot.addWidget(ventana)
    assert ventana.herramienta("editor").sesion is None


def test_lotes_abre_la_imagen_en_el_editor(qtbot, escribir_png, tmp_path):
    ventana = crear_ventana([])
    qtbot.addWidget(ventana)
    assert [ventana.lista.item(i).text() for i in range(ventana.lista.count())] == ["Quitar fondo", "Lotes"]
    ventana.mostrar("lotes").abrir_en_editor.emit(escribir_png(tmp_path / "b.png"))
    assert ventana.actual().id == "editor"
    assert ventana.herramienta("editor").sesion.doc.path.name == "b.png"
