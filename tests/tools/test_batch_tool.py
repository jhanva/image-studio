import time

import pytest

from image_studio.core.export import ExportSettings
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.tools.batch.panel import BatchTool


class RemovedorLento:
    def __init__(self, base, espera=0.0):
        self.base = base
        self.espera = espera

    def run(self, doc, ajustes, usar_alfa_existente=False):
        time.sleep(self.espera)
        return self.base.run(doc, ajustes)


def _panel(qtbot, removedor):
    panel = BatchTool(RemoverCache(lambda modelo, dispositivo, progreso: removedor), PresetStore())
    qtbot.addWidget(panel)
    panel.show()
    return panel


@pytest.fixture
def carpetas(tmp_path, escribir_png):
    entrada = tmp_path / "entrada"
    for nombre in ("a.png", "b.png", "c.png"):
        escribir_png(entrada / nombre)
    (entrada / "roto.png").write_bytes(b"x")
    return entrada, tmp_path / "salida"


def test_procesa_la_carpeta_y_llena_la_tabla(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    assert panel.ocupado and not panel.boton_iniciar.isEnabled()
    qtbot.waitUntil(lambda: not panel.ocupado)
    assert panel.tabla.rowCount() == 4
    estados = [panel.tabla.item(fila, 1).text() for fila in range(4)]
    assert estados == ["ok", "ok", "ok", "error"]
    assert panel.barra.value() == 4
    assert (salida / "informe.csv").exists()
    assert "Lote terminado: 3 ok, 0 baja confianza, 1 con error" in panel.ultimo_mensaje


def test_doble_clic_pide_abrir_en_el_editor(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    qtbot.waitUntil(lambda: not panel.ocupado)
    with qtbot.waitSignal(panel.abrir_en_editor) as senal:
        panel._abrir_fila(panel.tabla.item(1, 0))
    assert senal.args == [entrada / "b.png"]


def test_carpeta_de_entrada_inexistente(qtbot, tmp_path, removedor_falso):
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(tmp_path / "no"))
    panel.edit_salida.setText(str(tmp_path / "salida"))
    panel.iniciar()
    assert not panel.ocupado
    assert "no existe" in panel.ultimo_mensaje


def test_cancelar_detiene_el_lote(qtbot, tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    for i in range(20):
        escribir_png(entrada / f"{i:02d}.png")
    panel = _panel(qtbot, RemovedorLento(removedor_falso, espera=0.05))
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(tmp_path / "salida"))
    panel.iniciar()
    panel.cancelar()
    qtbot.waitUntil(lambda: not panel.ocupado, timeout=10000)
    assert panel.tabla.rowCount() < 20
    assert "cancelado" in panel.ultimo_mensaje


def test_usa_la_exportacion_elegida(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.set_exportacion(ExportSettings(formato="webp"))
    assert "webp" in panel.etiqueta_exportacion.text()
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    qtbot.waitUntil(lambda: not panel.ocupado)
    assert (salida / "a.webp").exists()
