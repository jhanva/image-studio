"""Lienzo: tablero de transparencia, zoom, desplazamiento y trazos de pincel."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from image_studio.core.brush import Rect
from image_studio.ui.canvas.layer import ImageLayer

FONDO_VISTA = QColor(45, 45, 48)


def _patron_ajedrez(lado: int = 8) -> QBrush:
    imagen = QImage(2 * lado, 2 * lado, QImage.Format.Format_RGB32)
    imagen.fill(QColor(204, 204, 204))
    pintor = QPainter(imagen)
    pintor.fillRect(0, 0, lado, lado, QColor(153, 153, 153))
    pintor.fillRect(lado, lado, lado, lado, QColor(153, 153, 153))
    pintor.end()
    return QBrush(imagen)


class CanvasView(QGraphicsView):
    trazo_inicio = Signal(QPointF)
    trazo_mueve = Signal(QPointF)
    trazo_fin = Signal()
    ESCALA_MIN = 0.02
    ESCALA_MAX = 32.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.capa = ImageLayer()
        self.scene().addItem(self.capa)
        self._cursor = QGraphicsEllipseItem()
        pluma = QPen(QColor(255, 255, 255))
        pluma.setCosmetic(True)
        self._cursor.setPen(pluma)
        self._cursor.setZValue(10)
        self._cursor.hide()
        self.scene().addItem(self._cursor)
        self.ruta_refinar = QPainterPath()
        self._vista_refinar = QGraphicsPathItem()
        self._vista_refinar.setZValue(5)
        self.scene().addItem(self._vista_refinar)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # El tablero está fijo a la pantalla, así que hay que repintar todo al desplazar.
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)
        self.pintura_habilitada = False
        self._radio = 30.0
        self._pintando = False
        self._paneo: QPointF | None = None
        self._ajedrez = _patron_ajedrez()

    @property
    def escala(self) -> float:
        return self.transform().m11()

    def set_images(self, despues: QImage, antes: QImage) -> None:
        self.capa.set_images(despues, antes)
        self.scene().setSceneRect(self.capa.boundingRect())
        self.ajustar()

    def ajustar(self) -> None:
        if not self.capa.boundingRect().isEmpty():
            self.fitInView(self.capa, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_real(self) -> None:
        self.resetTransform()

    def zoom(self, factor: float) -> None:
        objetivo = min(max(self.escala * factor, self.ESCALA_MIN), self.ESCALA_MAX)
        relativo = objetivo / self.escala
        self.scale(relativo, relativo)

    def actualizar(self, rect: Rect) -> None:
        x0, y0, x1, y1 = rect
        self.capa.update(QRectF(x0, y0, x1 - x0, y1 - y0))

    def set_brush_radius(self, radio: float) -> None:
        self._radio = radio
        self._mover_cursor(self._cursor.rect().center())

    def iniciar_vista_refinar(self, radio: float, punto: QPointF) -> None:
        pluma = QPen(QColor(255, 0, 170, 110), 2 * radio)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._vista_refinar.setPen(pluma)
        self.ruta_refinar = QPainterPath(punto)
        self.ruta_refinar.lineTo(punto)
        self._vista_refinar.setPath(self.ruta_refinar)

    def agregar_punto_refinar(self, punto: QPointF) -> None:
        self.ruta_refinar.lineTo(punto)
        self._vista_refinar.setPath(self.ruta_refinar)

    def limpiar_vista_refinar(self) -> None:
        self.ruta_refinar = QPainterPath()
        self._vista_refinar.setPath(self.ruta_refinar)

    def wheelEvent(self, evento) -> None:
        pasos = evento.angleDelta().y() / 120
        if pasos:
            self.zoom(1.25**pasos)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.MiddleButton:
            self._paneo = evento.position()
            return
        if (
            evento.button() == Qt.MouseButton.LeftButton
            and self.pintura_habilitada
            and not self.capa.boundingRect().isEmpty()
        ):
            self._pintando = True
            self.trazo_inicio.emit(self.mapToScene(evento.position().toPoint()))
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:
        punto = self.mapToScene(evento.position().toPoint())
        self._mover_cursor(punto)
        if self._paneo is not None:
            delta = evento.position() - self._paneo
            self._paneo = evento.position()
            barra_h, barra_v = self.horizontalScrollBar(), self.verticalScrollBar()
            barra_h.setValue(barra_h.value() - int(delta.x()))
            barra_v.setValue(barra_v.value() - int(delta.y()))
            return
        if self._pintando:
            self.trazo_mueve.emit(punto)
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.MiddleButton:
            self._paneo = None
            return
        if evento.button() == Qt.MouseButton.LeftButton and self._pintando:
            self._pintando = False
            self.trazo_fin.emit()
            return
        super().mouseReleaseEvent(evento)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.resetTransform()
        painter.fillRect(self.viewport().rect(), FONDO_VISTA)
        if not self.capa.boundingRect().isEmpty():
            zona = self.mapFromScene(self.capa.boundingRect()).boundingRect()
            painter.fillRect(zona, self._ajedrez)
        painter.restore()

    def _mover_cursor(self, centro: QPointF) -> None:
        r = self._radio
        self._cursor.setRect(centro.x() - r, centro.y() - r, 2 * r, 2 * r)
        self._cursor.setVisible(self.pintura_habilitada)
