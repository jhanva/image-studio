import json

import pytest

from image_studio.pipeline.presets_store import PresetStore, config_dir
from image_studio.pipeline.settings import PRESETS, PipelineSettings


def test_la_carpeta_de_configuracion_respeta_la_variable(tmp_path):
    assert config_dir() == tmp_path / "config"


def test_sin_archivo_solo_hay_presets_incluidos():
    almacen = PresetStore()
    assert almacen.todos() == PRESETS
    assert almacen.propios() == {}


def test_guardar_y_releer():
    PresetStore().guardar("Camisetas ñ", PipelineSettings(modelo="isnet", banda_px=6))
    releido = PresetStore().todos()
    assert releido["Camisetas ñ"] == PipelineSettings(modelo="isnet", banda_px=6)
    assert list(releido)[: len(PRESETS)] == list(PRESETS)


def test_archivo_en_utf8(tmp_path):
    PresetStore().guardar("Camisetas ñ", PipelineSettings())
    texto = (tmp_path / "config" / "presets.json").read_text(encoding="utf-8")
    assert json.loads(texto)["presets"]["Camisetas ñ"]["modelo"] == "auto"


def test_nombres_invalidos():
    almacen = PresetStore()
    with pytest.raises(ValueError):
        almacen.guardar("  ", PipelineSettings())
    with pytest.raises(ValueError):
        almacen.guardar("producto", PipelineSettings())


def test_borrar():
    almacen = PresetStore()
    almacen.guardar("x", PipelineSettings())
    almacen.borrar("x")
    assert "x" not in almacen.todos()
    with pytest.raises(ValueError):
        almacen.borrar("persona")


def test_archivo_corrupto_no_rompe(tmp_path):
    ruta = tmp_path / "config" / "presets.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{no es json", encoding="utf-8")
    assert PresetStore().todos() == PRESETS


def test_entrada_invalida_se_ignora(tmp_path):
    ruta = tmp_path / "config" / "presets.json"
    ruta.parent.mkdir(parents=True)
    datos = {"version": 1, "presets": {"malo": {"modelo": "u2net"}, "bueno": {"banda_px": 4}}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert set(PresetStore().propios()) == {"bueno"}
