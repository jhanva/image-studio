"""Ventana de la suite: barra lateral de herramientas, panel activo y barra de estado."""

from __future__ import annotations

from PySide6.QtCore import QSize, QThreadPool
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from image_studio.tools.base import Tool


class MainWindow(QMainWindow):
    def __init__(self, herramientas: list[Tool]):
        super().__init__()
        self.setWindowTitle("Image Studio")
        self.resize(1400, 900)
        self._herramientas = list(herramientas)
        self.lista = QListWidget()
        self.lista.setFixedWidth(140)
        self.lista.setIconSize(QSize(24, 24))
        self.pila = QStackedWidget()
        for herramienta in self._herramientas:
            self.lista.addItem(QListWidgetItem(herramienta.icono(), herramienta.nombre))
            self.pila.addWidget(herramienta)
            herramienta.mensaje.connect(self.statusBar().showMessage)
        self.lista.currentRowChanged.connect(self._cambiar)
        central = QWidget()
        diseno = QHBoxLayout(central)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.setSpacing(0)
        diseno.addWidget(self.lista)
        diseno.addWidget(self.pila)
        self.setCentralWidget(central)
        self.lista.setCurrentRow(0)
        self.etiqueta_equipo = QLabel("")
        self.statusBar().addPermanentWidget(self.etiqueta_equipo)

    def herramienta(self, id_: str) -> Tool:
        return next(h for h in self._herramientas if h.id == id_)

    def mostrar_equipo(self, texto: str) -> None:
        self.etiqueta_equipo.setText(texto)

    def actual(self) -> Tool:
        return self.pila.currentWidget()

    def mostrar(self, id_: str) -> Tool:
        herramienta = self.herramienta(id_)
        self.lista.setCurrentRow(self._herramientas.index(herramienta))
        return herramienta

    def _cambiar(self, fila: int) -> None:
        self.pila.setCurrentIndex(fila)
        self.statusBar().showMessage(self.actual().ultimo_mensaje)

    def closeEvent(self, evento) -> None:
        for herramienta in self._herramientas:
            herramienta.detener()
        # Un hilo de trabajo vivo al cerrar Python puede terminar el proceso con error.
        QThreadPool.globalInstance().waitForDone()
        super().closeEvent(evento)
