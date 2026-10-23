from PySide6.QtWidgets import QStyle

from image_studio.tools.base import Tool


class Prueba(Tool):
    id = "prueba"
    nombre = "Prueba"
    icono_estandar = QStyle.StandardPixmap.SP_DirOpenIcon


def test_icono_y_datos(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    assert herramienta.id == "prueba" and herramienta.nombre == "Prueba"
    assert not herramienta.icono().isNull()


def test_informar_emite_y_recuerda(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    recibidos = []
    herramienta.mensaje.connect(recibidos.append)
    herramienta.informar("hola")
    assert recibidos == ["hola"] and herramienta.ultimo_mensaje == "hola"


def test_detener_por_defecto_no_hace_nada(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    herramienta.detener()
