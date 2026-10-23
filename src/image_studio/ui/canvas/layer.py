"""Capa que dibuja el recorte (o el original) leyendo directo del buffer numpy."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem


class ImageLayer(QGraphicsItem):
    def __init__(self):
        super().__init__()
        # exposedRect permite dibujar solo la zona visible o actualizada.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self._despues: QImage | None = None
        self._antes: QImage | None = None
        self._mostrar_antes = False

    @property
    def mostrando_antes(self) -> bool:
        return self._mostrar_antes

    def set_images(self, despues: QImage, antes: QImage) -> None:
        self.prepareGeometryChange()
        self._despues = despues
        self._antes = antes
        self.update()

    def set_show_before(self, valor: bool) -> None:
        self._mostrar_antes = valor
        self.update()

    def boundingRect(self) -> QRectF:
        if self._despues is None:
            return QRectF()
        return QRectF(0, 0, self._despues.width(), self._despues.height())

    def paint(self, painter: QPainter, option, widget=None) -> None:
        imagen = self._antes if self._mostrar_antes else self._despues
        if imagen is None:
            return
        expuesta = option.exposedRect
        zona = expuesta if expuesta.isValid() and not expuesta.isEmpty() else self.boundingRect()
        zona = zona.intersected(self.boundingRect())
        if zona.isEmpty():
            return
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, painter.worldTransform().m11() < 1.0
        )
        painter.drawImage(zona, imagen, zona)
