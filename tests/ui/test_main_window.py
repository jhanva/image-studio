from PySide6.QtWidgets import QStyle

from image_studio.tools.base import Tool
from image_studio.ui.main_window import MainWindow


class Uno(Tool):
    id = "uno"
    nombre = "Uno"


class Dos(Tool):
    id = "dos"
    nombre = "Dos"
    icono_estandar = QStyle.StandardPixmap.SP_DirOpenIcon

    def __init__(self):
        super().__init__()
        self.detenida = False

    def detener(self):
        self.detenida = True


def _ventana(qtbot):
    herramientas = [Uno(), Dos()]
    ventana = MainWindow(herramientas)
    qtbot.addWidget(ventana)
    ventana.show()
    return ventana, herramientas


def test_lista_las_herramientas_y_muestra_la_primera(qtbot):
    ventana, (uno, _dos) = _ventana(qtbot)
    assert [ventana.lista.item(i).text() for i in range(ventana.lista.count())] == ["Uno", "Dos"]
    assert ventana.actual() is uno


def test_cambiar_de_herramienta(qtbot):
    ventana, (_uno, dos) = _ventana(qtbot)
    assert ventana.mostrar("dos") is dos
    assert ventana.actual() is dos and ventana.lista.currentRow() == 1
    ventana.lista.setCurrentRow(0)
    assert ventana.actual().id == "uno"


def test_mensajes_van_a_la_barra_de_estado(qtbot):
    ventana, (uno, _dos) = _ventana(qtbot)
    uno.informar("hola")
    assert ventana.statusBar().currentMessage() == "hola"


def test_cerrar_detiene_las_herramientas(qtbot):
    ventana, (_uno, dos) = _ventana(qtbot)
    ventana.close()
    assert dos.detenida
