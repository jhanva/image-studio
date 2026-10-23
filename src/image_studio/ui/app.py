"""Arranque de la interfaz gráfica y tema oscuro."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from image_studio.engines.warmup import prepare_engines
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.tools.background_removal.editor import EditorTool
from image_studio.tools.base import Tool
from image_studio.tools.batch.panel import BatchTool
from image_studio.ui.main_window import MainWindow
from image_studio.workers.tasks import ejecutar

FONDO_VENTANA = QColor(53, 53, 57)
FONDO_CAMPOS = QColor(37, 37, 40)
TEXTO = QColor(225, 225, 225)
TEXTO_DESACTIVADO = QColor(120, 120, 120)
ACENTO = QColor(64, 128, 214)


def aplicar_tema(app: QApplication) -> None:
    app.setStyle("Fusion")
    paleta = QPalette()
    rol = QPalette.ColorRole
    for papel, color in (
        (rol.Window, FONDO_VENTANA),
        (rol.WindowText, TEXTO),
        (rol.Base, FONDO_CAMPOS),
        (rol.AlternateBase, FONDO_VENTANA),
        (rol.ToolTipBase, FONDO_VENTANA),
        (rol.ToolTipText, TEXTO),
        (rol.Text, TEXTO),
        (rol.Button, FONDO_VENTANA),
        (rol.ButtonText, TEXTO),
        (rol.Highlight, ACENTO),
        (rol.HighlightedText, QColor(255, 255, 255)),
        (rol.PlaceholderText, TEXTO_DESACTIVADO),
    ):
        paleta.setColor(papel, color)
    for papel in (rol.Text, rol.ButtonText, rol.WindowText):
        paleta.setColor(QPalette.ColorGroup.Disabled, papel, TEXTO_DESACTIVADO)
    app.setPalette(paleta)


def crear_herramientas(cache: RemoverCache, presets: PresetStore | None = None) -> list[Tool]:
    presets = presets or PresetStore()
    return [EditorTool(cache, presets), BatchTool(cache, presets)]


def crear_ventana(rutas: list[str]) -> MainWindow:
    cache = RemoverCache()
    herramientas = crear_herramientas(cache)
    ventana = MainWindow(herramientas)
    editor, lotes = ventana.herramienta("editor"), ventana.herramienta("lotes")
    lotes.abrir_en_editor.connect(lambda ruta: (ventana.mostrar("editor"), editor.abrir(ruta)))
    # Los presets creados en una herramienta aparecen en la otra al cambiar de panel.
    ventana.lista.currentRowChanged.connect(lambda *_: (editor.recargar_presets(), lotes.recargar_presets()))
    eleccion = choose("auto", cache.hardware)
    ventana.mostrar_equipo(f"{cache.hardware.describir()} | automático: {eleccion.descripcion}")
    ventana.statusBar().showMessage("Preparando el motor (la primera vez puede tardar un minuto)...")
    ejecutar(
        prepare_engines,
        al_terminar=lambda segundos: ventana.statusBar().showMessage(f"Motor listo ({segundos:.0f} s)"),
        al_fallar=lambda mensaje: ventana.statusBar().showMessage(f"Error al preparar el motor: {mensaje}"),
    )
    if rutas:
        ventana.mostrar("editor").abrir(Path(rutas[0]))
    return ventana


def run(argv: list[str]) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Image Studio")
    aplicar_tema(app)
    ventana = crear_ventana(argv)
    ventana.show()
    return app.exec()
