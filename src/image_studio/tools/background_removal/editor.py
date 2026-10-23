"""Herramienta Quitar fondo: editor con pinceles, historial, presets y exportación."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QSpinBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
)

from image_studio.core.brush import Modo, Rect
from image_studio.core.export import ExportSettings
from image_studio.core.image_io import FORMATOS_ENTRADA, ImageDoc, ImageLoadError, load_image
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.session import EditSession, Pincel
from image_studio.pipeline.settings import PRESETS, PipelineSettings
from image_studio.tools.base import Tool
from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.export_dialog import ExportDialog
from image_studio.ui.preset_dialog import PresetDialog
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer, qimage_to_arrays
from image_studio.workers.tasks import ejecutar

FILTRO_IMAGENES = "Imágenes (" + " ".join(f"*{e}" for e in sorted(FORMATOS_ENTRADA)) + ")"


class EditorTool(Tool):
    id = "editor"
    nombre = "Quitar fondo"
    icono_estandar = QStyle.StandardPixmap.SP_FileDialogContentsView

    def __init__(self, cache: RemoverCache, presets: PresetStore, matter=None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._cache = cache
        self._presets = presets
        self._matter = matter if matter is not None else ClassicMatter()
        self.sesion: EditSession | None = None
        self._despues: RgbaBuffer | None = None
        self._antes: RgbBuffer | None = None
        self.ocupado = False
        self._exportacion = ExportSettings()
        self.barra = QToolBar("Editor")
        self.lienzo = CanvasView(self)
        self.lienzo.trazo_inicio.connect(self._trazo_inicio)
        self.lienzo.trazo_mueve.connect(self._trazo_mueve)
        self.lienzo.trazo_fin.connect(self._trazo_fin)
        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.barra)
        diseno.addWidget(self.lienzo)
        self._crear_interfaz()
        self._actualizar_estado()
        self.informar("Abre una imagen (Ctrl+O), arrástrala aquí o pégala (Ctrl+V)")

    # Interfaz

    def _accion(self, texto: str, atajos: list[str], funcion, marcable: bool = False) -> QAction:
        accion = QAction(texto, self)
        accion.setShortcuts([QKeySequence(a) for a in atajos])
        accion.setCheckable(marcable)
        accion.triggered.connect(funcion)
        self.addAction(accion)
        return accion

    def _crear_interfaz(self) -> None:
        self.accion_abrir = self._accion("Abrir...", ["Ctrl+O"], lambda *_: self._abrir_dialogo())
        self.accion_pegar = self._accion("Pegar", ["Ctrl+V"], lambda *_: self.pegar())
        self.accion_guardar = self._accion("Guardar PNG...", ["Ctrl+S"], lambda *_: self._guardar_dialogo())
        self.accion_quitar = self._accion("Quitar fondo", ["Ctrl+R"], lambda *_: self.quitar_fondo())
        self.accion_deshacer = self._accion("Deshacer", ["Ctrl+Z"], lambda *_: self.deshacer())
        self.accion_rehacer = self._accion("Rehacer", ["Ctrl+Y", "Ctrl+Shift+Z"], lambda *_: self.rehacer())
        self.accion_antes = self._accion(
            "Ver original", ["B"], lambda marcado: self.lienzo.capa.set_show_before(marcado), marcable=True
        )
        self.accion_ajustar = self._accion("Ajustar", ["Ctrl+0"], lambda *_: self.lienzo.ajustar())
        self.accion_100 = self._accion("100%", ["Ctrl+1"], lambda *_: self.lienzo.zoom_real())
        self.accion_exportar = self._accion("Exportar...", ["Ctrl+Shift+S"], lambda *_: self._exportar_dialogo())
        self.accion_guardar_preset = self._accion("Guardar preset...", [], lambda *_: self._guardar_preset_dialogo())
        self.accion_borrar_preset = self._accion("Borrar preset", [], lambda *_: self.borrar_preset(self.combo_preset.currentText()))

        grupo = QActionGroup(self)
        self._herramientas: list[tuple[QAction, Modo | None]] = []
        for texto, atajo, modo in (
            ("Mover", "V", None),
            ("Conservar", "K", Modo.CONSERVAR),
            ("Borrar", "E", Modo.BORRAR),
            ("Refinar borde", "R", Modo.REFINAR),
        ):
            accion = self._accion(texto, [atajo], lambda *_: self._actualizar_estado(), marcable=True)
            grupo.addAction(accion)
            self._herramientas.append((accion, modo))
        self.accion_mover, self.accion_conservar, self.accion_borrar, self.accion_refinar = (
            a for a, _ in self._herramientas
        )
        self.accion_mover.setChecked(True)

        self.combo_preset = QComboBox()
        self.combo_preset.currentTextChanged.connect(lambda *_: self._actualizar_presets())
        self.recargar_presets("producto")
        self.spin_radio = QSpinBox()
        self.spin_radio.setRange(1, 500)
        self.spin_radio.setValue(30)
        self.spin_radio.valueChanged.connect(lambda valor: self.lienzo.set_brush_radius(float(valor)))
        self.spin_dureza = QSpinBox()
        self.spin_dureza.setRange(0, 100)
        self.spin_dureza.setValue(80)
        self.spin_dureza.setSuffix(" %")

        barra = self.barra
        barra.setMovable(False)
        for accion in (self.accion_abrir, self.accion_pegar, self.accion_guardar, self.accion_exportar):
            barra.addAction(accion)
        barra.addSeparator()
        barra.addWidget(QLabel(" Preset "))
        barra.addWidget(self.combo_preset)
        barra.addAction(self.accion_quitar)
        barra.addAction(self.accion_guardar_preset)
        barra.addAction(self.accion_borrar_preset)
        barra.addSeparator()
        for accion, _ in self._herramientas:
            barra.addAction(accion)
        barra.addWidget(QLabel(" Radio "))
        barra.addWidget(self.spin_radio)
        barra.addWidget(QLabel(" Dureza "))
        barra.addWidget(self.spin_dureza)
        barra.addSeparator()
        for accion in (self.accion_deshacer, self.accion_rehacer, self.accion_antes, self.accion_ajustar, self.accion_100):
            barra.addAction(accion)

    def recargar_presets(self, seleccion: str | None = None) -> None:
        actual = seleccion or self.combo_preset.currentText()
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItems(list(self._presets.todos()))
        self.combo_preset.setCurrentText(actual)
        self.combo_preset.blockSignals(False)
        self._actualizar_presets()

    def _ajustes_actuales(self) -> PipelineSettings:
        return self._presets.todos()[self.combo_preset.currentText()]

    def _modo_actual(self) -> Modo | None:
        return next((modo for accion, modo in self._herramientas if accion.isChecked()), None)

    def _actualizar_estado(self) -> None:
        hay = self.sesion is not None
        libre = not self.ocupado
        editable = hay and libre
        for accion in (self.accion_abrir, self.accion_pegar):
            accion.setEnabled(libre)
        for accion in (self.accion_guardar, self.accion_exportar, self.accion_quitar, self.accion_antes, self.accion_ajustar, self.accion_100):
            accion.setEnabled(editable)
        for accion, _ in self._herramientas:
            accion.setEnabled(editable)
        sin_trazo = editable and not self.sesion.trazo_abierto
        self.accion_deshacer.setEnabled(sin_trazo and self.sesion.history.puede_deshacer)
        self.accion_rehacer.setEnabled(sin_trazo and self.sesion.history.puede_rehacer)
        self.lienzo.pintura_habilitada = editable and self._modo_actual() is not None
        self.lienzo.set_brush_radius(float(self.spin_radio.value()))

    def _ocupar(self, mensaje: str) -> None:
        self.ocupado = True
        self.informar(mensaje)
        self._actualizar_estado()

    def _liberar(self) -> None:
        self.ocupado = False
        self._actualizar_estado()

    def _refrescar(self, rect: Rect | None) -> None:
        if rect is None or self._despues is None:
            return
        self._despues.update(self.sesion.rgb, self.sesion.alpha, rect)
        self.lienzo.actualizar(rect)

    # Abrir

    def abrir(self, ruta: str | Path) -> bool:
        try:
            doc = load_image(ruta)
        except ImageLoadError as exc:
            self.informar(str(exc))
            return False
        return self.cargar_doc(doc)

    def cargar_doc(self, doc: ImageDoc) -> bool:
        if self.ocupado:
            self.informar("Espera a que termine la tarea en curso")
            return False
        self.sesion = EditSession(doc)
        self._despues = RgbaBuffer(self.sesion.rgb, self.sesion.alpha)
        self._antes = RgbBuffer(doc.rgb)
        self.lienzo.set_images(self._despues.imagen, self._antes.imagen)
        self.accion_antes.setChecked(False)
        self.lienzo.capa.set_show_before(False)
        ancho, alto = doc.size
        self.informar(f"{doc.path.name}: {ancho}x{alto}")
        self._actualizar_estado()
        return True

    def cargar_qimage(self, imagen: QImage, nombre: str = "portapapeles.png") -> bool:
        rgb, alfa = qimage_to_arrays(imagen)
        return self.cargar_doc(ImageDoc(Path(nombre), rgb, alfa, None, None))

    def pegar(self) -> None:
        imagen = QApplication.clipboard().image()
        if imagen.isNull():
            self.informar("El portapapeles no tiene una imagen")
            return
        self.cargar_qimage(imagen)

    def _abrir_dialogo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir imagen", "", FILTRO_IMAGENES)
        if ruta:
            self.abrir(Path(ruta))

    def dragEnterEvent(self, evento) -> None:
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:
        rutas = [Path(url.toLocalFile()) for url in evento.mimeData().urls() if url.isLocalFile()]
        if rutas:
            self.abrir(rutas[0])

    # Quitar fondo

    def quitar_fondo(self) -> None:
        if self.sesion is None or self.ocupado:
            return
        self._ocupar(f"Quitando fondo ({self.combo_preset.currentText()})...")
        ejecutar(
            self._ejecutar_removedor,
            self.sesion.doc,
            self._ajustes_actuales(),
            al_terminar=self._fondo_quitado,
            al_fallar=self._tarea_fallida,
        )

    def _ejecutar_removedor(self, doc, ajustes):
        # Corre en un hilo de trabajo; la primera vez carga el modelo (BiRefNet tarda unos 11 s).
        return self._cache.run(doc, ajustes)

    def _fondo_quitado(self, resultado) -> None:
        self._liberar()
        self._refrescar(self.sesion.apply_result(resultado))
        self._actualizar_estado()
        total = sum(resultado.tiempos.values())
        aviso = f" Revisar: {resultado.motivo_confianza}." if resultado.baja_confianza else ""
        self.informar(f"Fondo quitado en {total:.1f} s con {resultado.dispositivo}.{aviso}")

    def _tarea_fallida(self, mensaje: str) -> None:
        if self.sesion is not None and self.sesion.refinado_pendiente:
            self.sesion.cancel_refine()
            self.lienzo.limpiar_vista_refinar()
        self._liberar()
        self.informar(f"Error: {mensaje}")

    # Pinceles

    def _trazo_inicio(self, punto: QPointF) -> None:
        modo = self._modo_actual()
        if self.sesion is None or self.ocupado or modo is None:
            return
        self.sesion.pincel = Pincel(modo, float(self.spin_radio.value()), self.spin_dureza.value() / 100)
        if modo is Modo.REFINAR:
            self.lienzo.iniciar_vista_refinar(self.sesion.pincel.radio, punto)
        self._refrescar(self.sesion.begin_stroke(punto.x(), punto.y()))

    def _trazo_mueve(self, punto: QPointF) -> None:
        if self.sesion is None or self.ocupado or not self.sesion.trazo_abierto:
            return
        if self.sesion.pincel.modo is Modo.REFINAR:
            self.lienzo.agregar_punto_refinar(punto)
        self._refrescar(self.sesion.move_stroke(punto.x(), punto.y()))

    def _trazo_fin(self) -> None:
        if self.sesion is None or self.ocupado:
            return
        self.sesion.end_stroke()
        if self.sesion.refinado_pendiente:
            self._ocupar("Refinando borde...")
            ejecutar(
                self.sesion.refine_pending,
                self._matter,
                al_terminar=self._borde_refinado,
                al_fallar=self._tarea_fallida,
            )
            return
        self._actualizar_estado()

    def _borde_refinado(self, rect: Rect | None) -> None:
        self.lienzo.limpiar_vista_refinar()
        self._liberar()
        self._refrescar(rect)
        self.informar("Borde refinado")

    # Historial y guardado

    def deshacer(self) -> None:
        if self.sesion is None or self.ocupado or self.sesion.trazo_abierto:
            return
        for rect in self.sesion.undo():
            self._refrescar(rect)
        self._actualizar_estado()

    def rehacer(self) -> None:
        if self.sesion is None or self.ocupado or self.sesion.trazo_abierto:
            return
        for rect in self.sesion.redo():
            self._refrescar(rect)
        self._actualizar_estado()

    def _guardar_dialogo(self) -> None:
        if self.sesion is None:
            return
        sugerido = str(self.sesion.doc.path.with_suffix(".png"))
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar PNG", sugerido, "PNG (*.png)")
        if ruta:
            self.guardar_en(Path(ruta))

    def guardar_en(self, ruta: Path) -> Path | None:
        return self.exportar_en(ruta, ExportSettings())

    def exportar_en(self, ruta: Path, ajustes: ExportSettings) -> Path | None:
        if self.sesion is None or self.ocupado:
            return None
        limpiar = self.sesion.resultado is not None and self._ajustes_actuales().limpieza_color
        destino = self.sesion.export(ruta, ajustes, limpiar_color=limpiar)
        self.informar(f"Guardado: {destino}")
        return destino

    # Presets y exportación

    def _actualizar_presets(self) -> None:
        if hasattr(self, "accion_borrar_preset"):
            self.accion_borrar_preset.setEnabled(self.combo_preset.currentText() not in PRESETS)

    def guardar_preset(self, nombre: str, ajustes: PipelineSettings) -> None:
        nombre = self._presets.guardar(nombre, ajustes)
        self.recargar_presets(nombre)
        self.informar(f"Preset guardado: {nombre}")

    def borrar_preset(self, nombre: str) -> None:
        if nombre in PRESETS:
            return
        self._presets.borrar(nombre)
        self.recargar_presets("producto")
        self.informar(f"Preset borrado: {nombre}")

    def _guardar_preset_dialogo(self) -> None:
        dialogo = PresetDialog(self._ajustes_actuales(), set(PRESETS), self)
        if dialogo.exec():
            self.guardar_preset(*dialogo.valor())

    def _exportar_dialogo(self) -> None:
        if self.sesion is None:
            return
        dialogo = ExportDialog(self._exportacion, self)
        if not dialogo.exec():
            return
        self._exportacion = dialogo.ajustes()
        formato = self._exportacion.formato
        sugerido = str(self.sesion.doc.path.with_suffix("." + formato))
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar", sugerido, f"{formato.upper()} (*.{formato})")
        if ruta:
            self.exportar_en(Path(ruta), self._exportacion)
