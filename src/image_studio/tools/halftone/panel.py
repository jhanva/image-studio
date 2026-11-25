"""Herramienta Semitonos: knockout del color de la camiseta y degradado con semitonos (spec-semitonos)."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from image_studio.core.brush import Rect
from image_studio.core.export import ExportSettings, save
from image_studio.core.halftone.knockout import knockout_color
from image_studio.core.halftone.screen import screen_for
from image_studio.core.halftone.settings import (
    DPI_IMPRESION,
    AlphaMode,
    HalftoneSettings,
    KnockoutMode,
    Pattern,
)
from image_studio.core.image_io import FORMATOS_ENTRADA, ImageLoadError, load_image
from image_studio.pipeline.halftone_presets import HALFTONE_PRESETS, HalftonePresetStore
from image_studio.pipeline.halftone_session import (
    ANCHO_MAX_PULGADAS,
    ANCHO_MIN_PULGADAS,
    Borrador,
    HalftoneSession,
    ModoBorrador,
)
from image_studio.tools.base import Tool
from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.qt_image import RgbaBuffer
from image_studio.workers.tasks import ejecutar

FILTRO_IMAGENES = "Imágenes (" + " ".join(f"*{e}" for e in sorted(FORMATOS_ENTRADA)) + ")"
ESPERA_MS = 150

NOMBRES_KNOCKOUT = {
    KnockoutMode.NEGRO: "Negro",
    KnockoutMode.BLANCO: "Blanco",
    KnockoutMode.AUTO: "Automático",
    KnockoutMode.ELEGIDO: "Elegido del arte",
}
NOMBRES_PATRON = {
    Pattern.REDONDO: "Punto redondo",
    Pattern.DIAMANTE: "Diamante",
    Pattern.ELIPSE: "Elipse",
    Pattern.CUADRADO: "Cuadrado",
    Pattern.LINEA: "Línea",
    Pattern.LINEAS_ONDULADAS: "Líneas onduladas",
    Pattern.PUNTOS_ONDULADOS: "Puntos ondulados",
}
NOMBRES_ALFA = {AlphaMode.TRAMAR: "Tramarlos", AlphaMode.CORTAR: "Corte al 50%"}


class Deslizador(QWidget):
    """Barra y casilla numérica sincronizadas; el valor oficial es el de la casilla."""

    def __init__(self, minimo, maximo, paso, decimales=0, sufijo="", parent=None):
        super().__init__(parent)
        self._factor = 10**decimales
        self.casilla = QDoubleSpinBox()
        self.casilla.setRange(minimo, maximo)
        self.casilla.setSingleStep(paso)
        self.casilla.setDecimals(decimales)
        self.casilla.setSuffix(sufijo)
        self.casilla.setKeyboardTracking(False)
        self.barra = QSlider(Qt.Orientation.Horizontal)
        self.barra.setRange(round(minimo * self._factor), round(maximo * self._factor))
        self.barra.valueChanged.connect(lambda v: self.casilla.setValue(v / self._factor))
        self.casilla.valueChanged.connect(self._a_barra)
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.barra, 1)
        diseno.addWidget(self.casilla)
        self.valueChanged = self.casilla.valueChanged

    def _a_barra(self, valor: float) -> None:
        self.barra.blockSignals(True)
        self.barra.setValue(round(valor * self._factor))
        self.barra.blockSignals(False)

    def value(self) -> float:
        return self.casilla.value()

    def setValue(self, valor: float) -> None:
        self.casilla.setValue(valor)


def _muestra(color: tuple[int, int, int]) -> QPixmap:
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(*color))
    return pixmap


class HalftoneTool(Tool):
    id = "semitonos"
    nombre = "Semitonos"
    icono_estandar = QStyle.StandardPixmap.SP_DialogApplyButton

    def __init__(self, presets: HalftonePresetStore | None = None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._presets = presets or HalftonePresetStore()
        self.sesion: HalftoneSession | None = None
        self._datos: np.ndarray | None = None
        self._vista: QImage | None = None
        self._antes: RgbaBuffer | None = None
        self._color_elegido = (0, 0, 0)
        self._camiseta: tuple[int, int, int] | None = None
        self._cuentagotas: str | None = None
        self.calculando = False
        self._pendiente = False
        self.generacion_completa = -1
        self.ultimo_tiempo_ms = 0.0
        self._cargando_controles = False
        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(ESPERA_MS)
        self._temporizador.timeout.connect(self.calcular)

        self.barra = QToolBar("Semitonos")
        self.lienzo = CanvasView(self)
        self.lienzo.trazo_inicio.connect(self._trazo_inicio)
        self.lienzo.trazo_mueve.connect(self._trazo_mueve)
        self.lienzo.trazo_fin.connect(self._trazo_fin)
        self.controles = self._crear_controles()
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(self.controles)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desplazable.setFixedWidth(420)
        derecha = QVBoxLayout()
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.addWidget(self.barra)
        derecha.addWidget(self.lienzo)
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(desplazable)
        diseno.addLayout(derecha, 1)
        self._crear_barra()
        self.recargar_presets("Camiseta negra")
        self._actualizar_estado()
        self.informar("Abre un diseño (Ctrl+O) o arrástralo aquí")

    # Interfaz

    def _accion(self, texto: str, atajos: list[str], funcion, marcable: bool = False) -> QAction:
        accion = QAction(texto, self)
        accion.setShortcuts([QKeySequence(a) for a in atajos])
        accion.setCheckable(marcable)
        accion.triggered.connect(funcion)
        self.addAction(accion)
        return accion

    def _combo(self, nombres: dict) -> QComboBox:
        combo = QComboBox()
        for valor, texto in nombres.items():
            combo.addItem(texto, valor.value)
        combo.currentIndexChanged.connect(lambda *_: self._cambio())
        return combo

    def _casilla(self, texto: str) -> QCheckBox:
        casilla = QCheckBox(texto)
        casilla.toggled.connect(lambda *_: self._cambio())
        return casilla

    def _deslizador(self, *args, **kwargs) -> Deslizador:
        control = Deslizador(*args, **kwargs)
        control.valueChanged.connect(lambda *_: self._cambio())
        return control

    def _crear_controles(self) -> QWidget:
        panel = QWidget()
        columna = QVBoxLayout(panel)

        grupo = QGroupBox("Preset")
        fila = QHBoxLayout(grupo)
        self.combo_preset = QComboBox()
        self.combo_preset.activated.connect(lambda *_: self.aplicar_preset(self.combo_preset.currentText()))
        self.boton_guardar_preset = QPushButton("Guardar...")
        self.boton_guardar_preset.clicked.connect(self._guardar_preset_dialogo)
        self.boton_borrar_preset = QPushButton("Borrar")
        self.boton_borrar_preset.clicked.connect(lambda: self.borrar_preset(self.combo_preset.currentText()))
        fila.addWidget(self.combo_preset, 1)
        fila.addWidget(self.boton_guardar_preset)
        fila.addWidget(self.boton_borrar_preset)
        columna.addWidget(grupo)

        grupo = QGroupBox("Color a eliminar (color de la camiseta)")
        forma = QFormLayout(grupo)
        self.combo_knockout = self._combo(NOMBRES_KNOCKOUT)
        self.boton_tomar_knockout = QPushButton("Tomar del arte")
        self.boton_tomar_knockout.clicked.connect(lambda: self.activar_cuentagotas("knockout"))
        self.muestra_knockout = QLabel()
        fila = QHBoxLayout()
        fila.addWidget(self.combo_knockout, 1)
        fila.addWidget(self.muestra_knockout)
        fila.addWidget(self.boton_tomar_knockout)
        forma.addRow(fila)
        columna.addWidget(grupo)

        grupo = QGroupBox("Limpieza")
        forma = QFormLayout(grupo)
        self.casilla_fondo = self._casilla("Quitar el fondo sólido alrededor del arte")
        self.casilla_interior = self._casilla("Quitar también ese color dentro del arte")
        self.lista_colores = QListWidget()
        self.lista_colores.setMaximumHeight(70)
        self.boton_agregar_color = QPushButton("Agregar color a borrar")
        self.boton_agregar_color.clicked.connect(lambda: self.activar_cuentagotas("borrar"))
        self.boton_quitar_color = QPushButton("Quitar")
        self.boton_quitar_color.clicked.connect(self._quitar_color)
        fila = QHBoxLayout()
        fila.addWidget(self.boton_agregar_color)
        fila.addWidget(self.boton_quitar_color)
        self.control_tolerancia = self._deslizador(0, 50, 1, sufijo=" %")
        self.control_encoger = self._deslizador(0, 10, 1, sufijo=" px")
        forma.addRow(self.casilla_fondo)
        forma.addRow(self.casilla_interior)
        forma.addRow(self.lista_colores)
        forma.addRow(fila)
        forma.addRow("Tolerancia", self.control_tolerancia)
        forma.addRow("Encoger borde", self.control_encoger)
        columna.addWidget(grupo)

        grupo = QGroupBox("Trama")
        forma = QFormLayout(grupo)
        self.control_lpi = self._deslizador(10, 85, 1, sufijo=" LPI")
        self.control_angulo = self._deslizador(0, 180, 0.5, decimales=1, sufijo=" °")
        self.casilla_rejilla = self._casilla("Ajustar a la rejilla (sin moiré)")
        self.etiqueta_trama = QLabel()
        self.combo_patron = self._combo(NOMBRES_PATRON)
        forma.addRow("Frecuencia", self.control_lpi)
        forma.addRow("Ángulo", self.control_angulo)
        forma.addRow(self.casilla_rejilla)
        forma.addRow("Efectiva", self.etiqueta_trama)
        forma.addRow("Patrón", self.combo_patron)
        columna.addWidget(grupo)

        grupo = QGroupBox("Degradado")
        forma = QFormLayout(grupo)
        self.control_alcance = self._deslizador(1, 100, 1, sufijo=" %")
        self.control_peso = self._deslizador(-100, 100, 1)
        self.control_descartar = self._deslizador(0, 20, 0.5, decimales=1, sufijo=" %")
        self.combo_alfa = self._combo(NOMBRES_ALFA)
        self.control_bordes = self._deslizador(0, 10, 1, sufijo=" px")
        self.control_restaurar = self._deslizador(0, 100, 1, sufijo=" %")
        forma.addRow("Alcance", self.control_alcance)
        forma.addRow("Peso del punto", self.control_peso)
        forma.addRow("Descartar puntos", self.control_descartar)
        forma.addRow("Semitransparentes", self.combo_alfa)
        forma.addRow("Bordes limpios", self.control_bordes)
        forma.addRow("Restaurar color", self.control_restaurar)
        columna.addWidget(grupo)

        grupo = QGroupBox("Impresión")
        forma = QFormLayout(grupo)
        self.casilla_ancho = QDoubleSpinBox()
        self.casilla_ancho.setRange(ANCHO_MIN_PULGADAS, ANCHO_MAX_PULGADAS)
        self.casilla_ancho.setDecimals(2)
        self.casilla_ancho.setSuffix(" in")
        self.casilla_ancho.setKeyboardTracking(False)
        self.casilla_ancho.valueChanged.connect(self.cambiar_ancho)
        self.etiqueta_pixeles = QLabel()
        forma.addRow("Ancho a 300 DPI", self.casilla_ancho)
        forma.addRow("Píxeles", self.etiqueta_pixeles)
        columna.addWidget(grupo)

        grupo = QGroupBox("Borradores")
        forma = QFormLayout(grupo)
        self.casilla_pincel = QDoubleSpinBox()
        self.casilla_pincel.setRange(0.05, 3.0)
        self.casilla_pincel.setSingleStep(0.05)
        self.casilla_pincel.setValue(0.30)
        self.casilla_pincel.setSuffix(" in")
        self.casilla_pincel.valueChanged.connect(lambda *_: self._actualizar_estado())
        forma.addRow("Tamaño del pincel", self.casilla_pincel)
        ayuda = QLabel("Proteger: zonas que no deben tramarse (texto pequeño, caras).")
        ayuda.setWordWrap(True)
        forma.addRow(ayuda)
        columna.addWidget(grupo)
        columna.addStretch(1)
        return panel

    def _crear_barra(self) -> None:
        self.accion_abrir = self._accion("Abrir...", ["Ctrl+O"], lambda *_: self._abrir_dialogo())
        self.accion_exportar = self._accion("Exportar PNG...", ["Ctrl+Shift+S"], lambda *_: self._exportar_dialogo())
        self.accion_deshacer = self._accion("Deshacer", ["Ctrl+Z"], lambda *_: self.deshacer())
        self.accion_rehacer = self._accion("Rehacer", ["Ctrl+Y", "Ctrl+Shift+Z"], lambda *_: self.rehacer())
        self.accion_limpiar = self._accion("Limpiar borradores", [], lambda *_: self.limpiar_borradores())
        self.accion_antes = self._accion(
            "Ver original", ["B"], lambda marcado: self.lienzo.capa.set_show_before(marcado), marcable=True
        )
        self.accion_camiseta = self._accion("Sobre camiseta", ["T"], lambda *_: self._actualizar_fondo(), marcable=True)
        self.accion_camiseta.setChecked(True)
        self.accion_color_camiseta = self._accion("Color de camiseta...", [], lambda *_: self._elegir_camiseta())
        self.accion_ajustar = self._accion("Ajustar", ["Ctrl+0"], lambda *_: self.lienzo.ajustar())
        self.accion_100 = self._accion("100%", ["Ctrl+1"], lambda *_: self.lienzo.zoom_real())
        self._accion("Pincel menor", ["["], lambda *_: self._cambiar_pincel(-0.05))
        self._accion("Pincel mayor", ["]"], lambda *_: self._cambiar_pincel(0.05))

        grupo = QActionGroup(self)
        self._herramientas: list[tuple[QAction, ModoBorrador | None]] = []
        for texto, atajo, modo in (
            ("Mover", "V", None),
            ("Borrar", "E", ModoBorrador.BORRAR),
            ("Proteger", "P", ModoBorrador.PROTEGER),
            ("Quitar marca", "Q", ModoBorrador.QUITAR),
        ):
            accion = self._accion(texto, [atajo], lambda *_: self._elegir_herramienta(), marcable=True)
            grupo.addAction(accion)
            self._herramientas.append((accion, modo))
        self.accion_mover, self.accion_borrar, self.accion_proteger, self.accion_quitar_marca = (
            a for a, _ in self._herramientas
        )
        self.accion_mover.setChecked(True)

        barra = self.barra
        barra.setMovable(False)
        for accion in (self.accion_abrir, self.accion_exportar):
            barra.addAction(accion)
        barra.addSeparator()
        for accion, _ in self._herramientas:
            barra.addAction(accion)
        for accion in (self.accion_deshacer, self.accion_rehacer, self.accion_limpiar):
            barra.addAction(accion)
        barra.addSeparator()
        for accion in (self.accion_camiseta, self.accion_color_camiseta, self.accion_antes,
                       self.accion_ajustar, self.accion_100):
            barra.addAction(accion)

    # Ajustes y controles

    def ajustes_actuales(self) -> HalftoneSettings:
        colores = tuple(
            self.lista_colores.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista_colores.count())
        )
        return HalftoneSettings(
            knockout=self.combo_knockout.currentData(),
            color_elegido=self._color_elegido,
            quitar_fondo=self.casilla_fondo.isChecked(),
            fondo_interior=self.casilla_interior.isChecked(),
            colores_borrar=colores,
            tolerancia=self.control_tolerancia.value(),
            encoger_px=int(self.control_encoger.value()),
            lpi=self.control_lpi.value(),
            angulo=self.control_angulo.value(),
            ajustar_rejilla=self.casilla_rejilla.isChecked(),
            patron=self.combo_patron.currentData(),
            alcance=self.control_alcance.value(),
            peso=self.control_peso.value(),
            descartar=self.control_descartar.value(),
            semitransparencia=self.combo_alfa.currentData(),
            bordes_limpios_px=int(self.control_bordes.value()),
            restaurar=self.control_restaurar.value(),
        )

    def cargar_ajustes(self, ajustes: HalftoneSettings) -> None:
        self._cargando_controles = True
        try:
            self.combo_knockout.setCurrentIndex(self.combo_knockout.findData(ajustes.knockout.value))
            self._color_elegido = ajustes.color_elegido
            self.casilla_fondo.setChecked(ajustes.quitar_fondo)
            self.casilla_interior.setChecked(ajustes.fondo_interior)
            self.lista_colores.clear()
            for color in ajustes.colores_borrar:
                self._agregar_item_color(color)
            self.control_tolerancia.setValue(ajustes.tolerancia)
            self.control_encoger.setValue(ajustes.encoger_px)
            self.control_lpi.setValue(ajustes.lpi)
            self.control_angulo.setValue(ajustes.angulo)
            self.casilla_rejilla.setChecked(ajustes.ajustar_rejilla)
            self.combo_patron.setCurrentIndex(self.combo_patron.findData(ajustes.patron.value))
            self.control_alcance.setValue(ajustes.alcance)
            self.control_peso.setValue(ajustes.peso)
            self.control_descartar.setValue(ajustes.descartar)
            self.combo_alfa.setCurrentIndex(self.combo_alfa.findData(ajustes.semitransparencia.value))
            self.control_bordes.setValue(ajustes.bordes_limpios_px)
            self.control_restaurar.setValue(ajustes.restaurar)
        finally:
            self._cargando_controles = False
        self._cambio()

    def _cambio(self) -> None:
        if self._cargando_controles:
            return
        ajustes = self.ajustes_actuales()
        pantalla = screen_for(ajustes)
        self.etiqueta_trama.setText(f"{pantalla.lpi:.1f} LPI a {pantalla.angulo:.1f}°")
        self.muestra_knockout.setPixmap(_muestra(self._knockout_mostrado(ajustes)))
        self._actualizar_fondo()
        self.programar()

    def _knockout_mostrado(self, ajustes: HalftoneSettings) -> tuple[int, int, int]:
        if self.sesion is None:
            return {KnockoutMode.BLANCO: (255, 255, 255), KnockoutMode.ELEGIDO: ajustes.color_elegido}.get(
                ajustes.knockout, (0, 0, 0)
            )
        return knockout_color(ajustes, self.sesion.rgb, self.sesion.alpha)

    def _agregar_item_color(self, color) -> None:
        item = QListWidgetItem(_muestra(color), f"RGB {color[0]}, {color[1]}, {color[2]}")
        item.setData(Qt.ItemDataRole.UserRole, tuple(color))
        self.lista_colores.addItem(item)

    def _quitar_color(self) -> None:
        fila = self.lista_colores.currentRow()
        if fila >= 0:
            self.lista_colores.takeItem(fila)
            self._cambio()

    # Presets

    def recargar_presets(self, seleccion: str | None = None) -> None:
        self.combo_preset.clear()
        self.combo_preset.addItems(list(self._presets.todos()))
        if seleccion is not None and self.combo_preset.findText(seleccion) >= 0:
            self.combo_preset.setCurrentText(seleccion)
            self.aplicar_preset(seleccion)
        self.boton_borrar_preset.setEnabled(self.combo_preset.currentText() not in HALFTONE_PRESETS)

    def aplicar_preset(self, nombre: str) -> None:
        ajustes = self._presets.todos().get(nombre)
        if ajustes is not None:
            self.cargar_ajustes(ajustes)
        self.boton_borrar_preset.setEnabled(nombre not in HALFTONE_PRESETS)

    def guardar_preset(self, nombre: str) -> None:
        try:
            nombre = self._presets.guardar(nombre, self.ajustes_actuales())
        except ValueError as exc:
            self.informar(str(exc))
            return
        self.recargar_presets(nombre)
        self.informar(f"Preset guardado: {nombre}")

    def borrar_preset(self, nombre: str) -> None:
        try:
            self._presets.borrar(nombre)
        except ValueError as exc:
            self.informar(str(exc))
            return
        self.recargar_presets("Camiseta negra")

    def _guardar_preset_dialogo(self) -> None:
        nombre, ok = QInputDialog.getText(self, "Guardar preset", "Nombre del preset:")
        if ok:
            self.guardar_preset(nombre)

    # Abrir

    def abrir(self, ruta: str | Path) -> bool:
        try:
            doc = load_image(ruta)
        except ImageLoadError as exc:
            self.informar(str(exc))
            return False
        if self.sesion is not None and self.sesion.trazo_abierto:
            self.sesion.end_stroke()
        self.sesion = HalftoneSession(doc, self.ajustes_actuales())
        self.casilla_ancho.blockSignals(True)
        self.casilla_ancho.setMaximum(self.sesion.ancho_maximo())
        self.casilla_ancho.setValue(self.sesion.ancho_pulgadas)
        self.casilla_ancho.blockSignals(False)
        self._preparar_buffers()
        self.informar(f"{doc.path.name}: {doc.size[0]}x{doc.size[1]}")
        self._cambio()
        self._actualizar_estado()
        return True

    def _preparar_buffers(self) -> None:
        alto, ancho = self.sesion.forma
        self._datos = np.zeros((alto, ancho, 4), np.uint8)
        self._vista = QImage(self._datos.data, ancho, alto, ancho * 4, QImage.Format.Format_RGBA8888)
        self._antes = RgbaBuffer(self.sesion.rgb, self.sesion.alpha)
        self.lienzo.set_images(self._vista, self._antes.imagen)
        self.accion_antes.setChecked(False)
        self.lienzo.capa.set_show_before(False)
        self.generacion_completa = -1
        self.etiqueta_pixeles.setText(f"{ancho} x {alto}")

    def cambiar_ancho(self, pulgadas: float) -> None:
        if self.sesion is None or self.sesion.trazo_abierto:
            return
        historial = self.sesion.history.puede_deshacer or self.sesion.history.puede_rehacer
        forma = self.sesion.forma
        if self.sesion.set_ancho(pulgadas):
            self.informar(f"El ancho se limitó a {self.sesion.ancho_pulgadas:.2f} in (máximo 60 MP)")
        self.casilla_ancho.blockSignals(True)
        self.casilla_ancho.setValue(self.sesion.ancho_pulgadas)
        self.casilla_ancho.blockSignals(False)
        if self.sesion.forma != forma:
            self._preparar_buffers()
            if historial:
                self.informar("Al cambiar el ancho se reinició el historial de borradores")
            self.programar()
        self._actualizar_estado()

    def _abrir_dialogo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir diseño", "", FILTRO_IMAGENES)
        if ruta:
            self.abrir(Path(ruta))

    def dragEnterEvent(self, evento) -> None:
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:
        rutas = [Path(url.toLocalFile()) for url in evento.mimeData().urls() if url.isLocalFile()]
        if rutas:
            self.abrir(rutas[0])

    # Cálculo en segundo plano

    def programar(self) -> None:
        """Pasa los ajustes a la sesión (la vista deja de estar al día) y espera a que se calmen."""
        if self.sesion is not None:
            self.sesion.set_ajustes(self.ajustes_actuales())
            self._temporizador.start()

    def _rect_visible(self) -> Rect | None:
        alto, ancho = self.sesion.forma
        zona = self.lienzo.mapToScene(self.lienzo.viewport().rect()).boundingRect()
        x0, y0 = max(0, int(zona.left()) - 1), max(0, int(zona.top()) - 1)
        x1, y1 = min(ancho, int(zona.right()) + 2), min(alto, int(zona.bottom()) + 2)
        if x0 >= x1 or y0 >= y1 or (x1 - x0) * (y1 - y0) >= ancho * alto * 0.6:
            return None
        return x0, y0, x1, y1

    def calcular(self) -> None:
        if self.sesion is None:
            return
        if self.calculando:
            self._pendiente = True
            return
        generacion = self.sesion.set_ajustes(self.ajustes_actuales())
        visible = self._rect_visible()
        self.calculando = True
        self._pendiente = False
        sesion = self.sesion

        def trabajo(reportar):
            inicio = time.perf_counter()
            if visible is not None:
                parcial = sesion.render(visible, generacion)
                if parcial is None:
                    return generacion, None, 0.0
                reportar((generacion, parcial))
            completo = sesion.render(None, generacion)
            return generacion, completo, (time.perf_counter() - inicio) * 1000

        ejecutar(
            trabajo,
            al_terminar=lambda r: self._calculo_listo(sesion, *r),
            al_fallar=self._calculo_fallido,
            al_avanzar=lambda r: self._mostrar(sesion, *r),
        )

    def _mostrar(self, sesion, generacion: int, resultado) -> bool:
        if resultado is None or sesion is not self.sesion or generacion != sesion.generacion:
            return False
        (x0, y0, x1, y1), rgba = resultado
        if self._datos is None or self._datos.shape[:2] != sesion.forma:
            return False
        self._datos[y0:y1, x0:x1] = rgba
        self.lienzo.actualizar((x0, y0, x1, y1))
        return True

    def _calculo_listo(self, sesion, generacion: int, resultado, tiempo_ms: float) -> None:
        self.calculando = False
        if self._mostrar(sesion, generacion, resultado):
            self.generacion_completa = generacion
            self.ultimo_tiempo_ms = tiempo_ms
            mensaje = f"Vista previa actualizada en {tiempo_ms:.0f} ms"
            if not HalftoneSession.hay_tinta(resultado[1]):
                mensaje += ". El resultado no tiene tinta"
            if sesion.ajustes.quitar_fondo and sesion.ultimo_fondo is None:
                mensaje += ". No se encontró un fondo sólido en el borde"
            self.informar(mensaje)
        if self._pendiente or (self.sesion is not None and self.generacion_completa != self.sesion.generacion
                               and not self._temporizador.isActive()):
            self.calcular()

    def _calculo_fallido(self, mensaje: str) -> None:
        self.calculando = False
        self.informar(f"Error al calcular: {mensaje}")

    @property
    def vista_al_dia(self) -> bool:
        return self.sesion is not None and self.generacion_completa == self.sesion.generacion

    # Vista

    def _actualizar_fondo(self) -> None:
        if not self.accion_camiseta.isChecked():
            self.lienzo.set_fondo(None)
            return
        color = self._camiseta or self._knockout_mostrado(self.ajustes_actuales())
        self.lienzo.set_fondo(QColor(*color))

    def _elegir_camiseta(self) -> None:
        inicial = QColor(*(self._camiseta or self._knockout_mostrado(self.ajustes_actuales())))
        color = QColorDialog.getColor(inicial, self, "Color de la camiseta")
        if color.isValid():
            self.fijar_color_camiseta((color.red(), color.green(), color.blue()))

    def fijar_color_camiseta(self, color: tuple[int, int, int] | None) -> None:
        """None sigue al color a eliminar."""
        self._camiseta = color
        self.accion_camiseta.setChecked(True)
        self._actualizar_fondo()

    # Cuentagotas y borradores

    def activar_cuentagotas(self, destino: str) -> None:
        """destino: 'knockout' o 'borrar'. El siguiente clic en el lienzo toma el color."""
        self._cuentagotas = destino
        self.informar("Haz clic en el diseño para tomar el color")
        self._actualizar_estado()

    def tomar_color(self, x: float, y: float) -> None:
        destino, self._cuentagotas = self._cuentagotas, None
        alto, ancho = self.sesion.forma
        xi, yi = min(max(int(x), 0), ancho - 1), min(max(int(y), 0), alto - 1)
        color = tuple(int(c) for c in self.sesion.rgb[yi, xi])
        if destino == "knockout":
            self._color_elegido = color
            self.combo_knockout.setCurrentIndex(self.combo_knockout.findData(KnockoutMode.ELEGIDO.value))
            self._cambio()
        elif destino == "borrar":
            self._agregar_item_color(color)
            self._cambio()
        self._actualizar_estado()

    def _modo_borrador(self) -> ModoBorrador | None:
        for accion, modo in self._herramientas:
            if accion.isChecked():
                return modo
        return None

    def _elegir_herramienta(self) -> None:
        self._cuentagotas = None
        self._actualizar_estado()

    def _cambiar_pincel(self, delta: float) -> None:
        self.casilla_pincel.setValue(self.casilla_pincel.value() + delta)

    def _radio_px(self) -> float:
        return max(0.5, self.casilla_pincel.value() * DPI_IMPRESION / 2)

    def _trazo_inicio(self, punto: QPointF) -> None:
        if self.sesion is None:
            return
        if self._cuentagotas is not None:
            self.tomar_color(punto.x(), punto.y())
            return
        modo = self._modo_borrador()
        if modo is None or self.sesion.trazo_abierto:
            return
        self.sesion.borrador = Borrador(modo, self._radio_px())
        self.sesion.begin_stroke(punto.x(), punto.y())
        self.programar()

    def _trazo_mueve(self, punto: QPointF) -> None:
        if self.sesion is not None and self.sesion.trazo_abierto:
            self.sesion.move_stroke(punto.x(), punto.y())
            self.programar()

    def _trazo_fin(self) -> None:
        if self.sesion is not None and self.sesion.trazo_abierto:
            self.sesion.end_stroke()
            self.programar()
            self._actualizar_estado()

    def deshacer(self) -> None:
        if self.sesion is None or self.sesion.trazo_abierto or not self.sesion.history.puede_deshacer:
            return
        self.sesion.undo()
        self.programar()
        self._actualizar_estado()

    def rehacer(self) -> None:
        if self.sesion is None or self.sesion.trazo_abierto or not self.sesion.history.puede_rehacer:
            return
        self.sesion.redo()
        self.programar()
        self._actualizar_estado()

    def limpiar_borradores(self) -> None:
        if self.sesion is None or self.sesion.trazo_abierto:
            return
        self.sesion.clear_marks()
        self.programar()
        self._actualizar_estado()

    # Exportar

    def exportar_en(self, ruta: str | Path, confirmar_sin_tinta: Callable[[], bool] | None = None) -> Path | None:
        if self.sesion is None:
            return None
        if self.sesion.trazo_abierto:
            self.sesion.end_stroke()
        self.sesion.set_ajustes(self.ajustes_actuales())
        _, salida = self.sesion.render()
        if not HalftoneSession.hay_tinta(salida):
            confirmar = confirmar_sin_tinta or self._confirmar_sin_tinta
            if not confirmar():
                return None
        destino = save(salida, Path(ruta), ExportSettings(formato="png", dpi=DPI_IMPRESION))
        self.informar(f"Exportado: {destino.name} ({salida.shape[1]}x{salida.shape[0]} a 300 DPI)")
        return destino

    def _confirmar_sin_tinta(self) -> bool:
        respuesta = QMessageBox.question(
            self, "Exportar", "El resultado no tiene tinta. ¿Exportar de todos modos?"
        )
        return respuesta == QMessageBox.StandardButton.Yes

    def _exportar_dialogo(self) -> None:
        if self.sesion is None:
            return
        sugerido = str(self.sesion.doc.path.with_name(self.sesion.doc.path.stem + "-semitonos.png"))
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", sugerido, "PNG (*.png)")
        if ruta:
            self.exportar_en(Path(ruta))

    # Estado

    def _actualizar_estado(self) -> None:
        hay = self.sesion is not None
        libre = hay and not self.sesion.trazo_abierto
        self.accion_exportar.setEnabled(hay)
        self.accion_deshacer.setEnabled(libre and self.sesion.history.puede_deshacer)
        self.accion_rehacer.setEnabled(libre and self.sesion.history.puede_rehacer)
        self.accion_limpiar.setEnabled(libre)
        self.casilla_ancho.setEnabled(libre)
        self.boton_tomar_knockout.setEnabled(hay)
        self.boton_agregar_color.setEnabled(hay)
        cuentagotas = self._cuentagotas is not None
        self.lienzo.pintura_habilitada = hay and (cuentagotas or self._modo_borrador() is not None)
        self.lienzo.set_brush_radius(2.0 if cuentagotas else self._radio_px())

    def detener(self) -> None:
        self._temporizador.stop()
        self._pendiente = False
