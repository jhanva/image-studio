import json

import pytest

from image_studio.core.halftone.settings import HalftoneSettings, KnockoutMode, Pattern
from image_studio.pipeline.halftone_presets import HALFTONE_PRESETS, HalftonePresetStore
from image_studio.pipeline.presets_store import PresetStore


def test_incluidos():
    todos = HalftonePresetStore().todos()
    assert list(todos) == ["Camiseta negra", "Camiseta blanca"]
    assert todos["Camiseta blanca"].knockout is KnockoutMode.BLANCO


def test_guardar_releer_y_borrar(tmp_path):
    ajustes = HalftoneSettings(patron=Pattern.ELIPSE, colores_borrar=[(1, 2, 3)])
    HalftonePresetStore().guardar("Vintage ñ", ajustes)
    assert HalftonePresetStore().todos()["Vintage ñ"] == ajustes
    texto = (tmp_path / "config" / "halftone_presets.json").read_text(encoding="utf-8")
    assert json.loads(texto)["presets"]["Vintage ñ"]["patron"] == "elipse"
    HalftonePresetStore().borrar("Vintage ñ")
    assert "Vintage ñ" not in HalftonePresetStore().todos()


def test_no_se_mezcla_con_los_presets_del_quitafondos():
    HalftonePresetStore().guardar("x", HalftoneSettings())
    assert "x" not in PresetStore().todos()


def test_nombres_invalidos_y_archivo_corrupto(tmp_path):
    with pytest.raises(ValueError):
        HalftonePresetStore().guardar("Camiseta negra", HalftoneSettings())
    with pytest.raises(ValueError):
        HalftonePresetStore().borrar("Camiseta blanca")
    ruta = tmp_path / "config" / "halftone_presets.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{roto", encoding="utf-8")
    assert HalftonePresetStore().todos() == HALFTONE_PRESETS
