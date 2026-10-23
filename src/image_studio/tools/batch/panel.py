"""Herramienta Lotes: quitar fondos de una carpeta con progreso, cancelación y tabla."""

from __future__ import annotations

import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_studio.core.export import ExportSettings
from image_studio.pipeline.batch import NOMBRE_INFORME, BatchItem, run_batch
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.tools.base import Tool
from image_studio.ui.export_dialog import ExportDialog
from image_studio.workers.tasks import ejecutar

COLUMNAS = ("Archivo", "Estado", "Tiempo (s)", "Motivo")


class BatchTool(Tool):
    id = "lotes"
    nombre = "Lotes"
    icono_estandar = QStyle.StandardPixmap.SP_FileDialogDetailedView
    abrir_en_editor = Signal(Path)

    def __init__(self, cache: RemoverCache, presets: PresetStore, parent=None):
        super().__init__(parent)
        self._cache = cache
        self._presets = presets
        self._exportacion = ExportSettings()
        self._cancelar = threading.Event()
        self._rutas: list[Path] = []
        self.ocupado = False

        self.edit_entrada = QLineEdit()
        self.edit_salida = QLineEdit()
        self.combo_preset = QComboBox()
        self.etiqueta_exportacion = QLabel()
        boton_exportacion = QPushButton("Exportación...")
        boton_exportacion.clicked.connect(self._elegir_exportacion)
        self.boton_iniciar = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Iniciar")
        self.boton_iniciar.clicked.connect(self.iniciar)
        self.boton_cancelar = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar)
        self.barra = QProgressBar()
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.itemDoubleClicked.connect(self._abrir_fila)

        formulario = QFormLayout()
        formulario.addRow("Entrada", self._con_boton(self.edit_entrada, "Carpeta de entrada"))
        formulario.addRow("Salida", self._con_boton(self.edit_salida, "Carpeta de salida"))
        formulario.addRow("Preset", self.combo_preset)
        fila_exportacion = QHBoxLayout()
        fila_exportacion.addWidget(self.etiqueta_exportacion, 1)
        fila_exportacion.addWidget(boton_exportacion)
        formulario.addRow("Exportación", fila_exportacion)
        botones = QHBoxLayout()
        botones.addWidget(self.boton_iniciar)
        botones.addWidget(self.boton_cancelar)
        botones.addWidget(self.barra, 1)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addLayout(botones)
        diseno.addWidget(self.tabla)

        self.recargar_presets()
        self.set_exportacion(self._exportacion)
        self._actualizar_estado()
        self.informar("Elige una carpeta de entrada y otra de salida")

    def _con_boton(self, campo: QLineEdit, titulo: str) -> QWidget:
        boton = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "")
        boton.clicked.connect(lambda: self._elegir_carpeta(campo, titulo))
        fila = QWidget()
        diseno = QHBoxLayout(fila)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(campo, 1)
        diseno.addWidget(boton)
        return fila

    def _elegir_carpeta(self, campo: QLineEdit, titulo: str) -> None:
        carpeta = QFileDialog.getExistingDirectory(self, titulo, campo.text())
        if carpeta:
            campo.setText(carpeta)

    def recargar_presets(self) -> None:
        actual = self.combo_preset.currentText() or "producto"
        self.combo_preset.clear()
        self.combo_preset.addItems(list(self._presets.todos()))
        self.combo_preset.setCurrentText(actual)

    def set_exportacion(self, ajustes: ExportSettings) -> None:
        self._exportacion = ajustes
        recorte = f", recorte {ajustes.margen_px} px" if ajustes.recortar else ""
        self.etiqueta_exportacion.setText(f"{ajustes.formato}, fondo {ajustes.fondo.value}{recorte}")

    def _elegir_exportacion(self) -> None:
        dialogo = ExportDialog(self._exportacion, self)
        if dialogo.exec():
            self.set_exportacion(dialogo.ajustes())

    def _actualizar_estado(self) -> None:
        self.boton_iniciar.setEnabled(not self.ocupado)
        self.boton_cancelar.setEnabled(self.ocupado)

    def iniciar(self) -> None:
        if self.ocupado:
            return
        entrada = Path(self.edit_entrada.text().strip())
        salida = Path(self.edit_salida.text().strip())
        if not self.edit_entrada.text().strip() or not entrada.is_dir():
            self.informar(f"La carpeta de entrada no existe: {entrada}")
            return
        if not self.edit_salida.text().strip():
            self.informar("Elige una carpeta de salida")
            return
        self.recargar_presets()
        ajustes = self._presets.todos()[self.combo_preset.currentText()]
        self._cancelar = threading.Event()
        self._rutas = []
        self.tabla.setRowCount(0)
        self.barra.setValue(0)
        self.ocupado = True
        self._actualizar_estado()
        self.informar(f"Procesando {entrada.name} con el preset {self.combo_preset.currentText()}...")
        ejecutar(
            self._correr,
            entrada,
            salida,
            ajustes,
            self._exportacion,
            self._cancelar,
            al_avanzar=self._avance,
            al_terminar=lambda items: self._terminado(items, salida),
            al_fallar=self._fallido,
        )

    def _correr(self, entrada, salida, ajustes, exportar, cancelar, reportar):
        # Corre en un hilo de trabajo; el modelo se carga una vez y lo comparte el editor.
        removedor = self._cache  # elige modelo y dispositivo y repite en CPU si la GPU falla
        return run_batch(
            entrada,
            salida,
            removedor,
            ajustes,
            exportar,
            progreso=lambda hechos, total, item: reportar((hechos, total, item)),
            cancelar=cancelar,
        )

    def _avance(self, dato) -> None:
        hechos, total, item = dato
        self.barra.setMaximum(total)
        self.barra.setValue(hechos)
        self._agregar_fila(item)

    def _agregar_fila(self, item: BatchItem) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        for columna, texto in enumerate((item.archivo.name, item.estado, f"{item.tiempo_s:.2f}", item.motivo)):
            self.tabla.setItem(fila, columna, QTableWidgetItem(texto))
        self._rutas.append(item.archivo)

    def _abrir_fila(self, celda: QTableWidgetItem) -> None:
        self.abrir_en_editor.emit(self._rutas[celda.row()])

    def _terminado(self, items: list[BatchItem], salida: Path) -> None:
        self.ocupado = False
        self._actualizar_estado()
        conteo = Counter(item.estado for item in items)
        inicio = "Lote cancelado" if self._cancelar.is_set() else "Lote terminado"
        self.informar(
            f"{inicio}: {conteo['ok']} ok, {conteo['baja_confianza']} baja confianza, "
            f"{conteo['error']} con error. Informe: {salida / NOMBRE_INFORME}"
        )

    def _fallido(self, mensaje: str) -> None:
        self.ocupado = False
        self._actualizar_estado()
        self.informar(f"Error: {mensaje}")

    def cancelar(self) -> None:
        self._cancelar.set()

    def detener(self) -> None:
        self.cancelar()
