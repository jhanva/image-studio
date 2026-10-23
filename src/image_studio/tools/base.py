"""Interfaz de las herramientas de la suite."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QWidget


class Tool(QWidget):
    """Un panel de la suite. La ventana lo muestra en la barra lateral y escucha sus mensajes."""

    id: str = ""
    nombre: str = ""
    icono_estandar = QStyle.StandardPixmap.SP_FileIcon
    mensaje = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ultimo_mensaje = ""

    def icono(self) -> QIcon:
        return self.style().standardIcon(self.icono_estandar)

    def informar(self, texto: str) -> None:
        self.ultimo_mensaje = texto
        self.mensaje.emit(texto)

    def detener(self) -> None:
        """Pide cancelar el trabajo en curso antes de cerrar la ventana."""
