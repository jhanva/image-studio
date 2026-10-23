import pytest

from image_studio.pipeline.settings import PRESETS, PipelineSettings


def test_presets_incluidos():
    assert set(PRESETS) == {"producto", "persona"}
    assert PRESETS["producto"].matting is False
    assert PRESETS["persona"].matting is True


def test_modelo_invalido():
    with pytest.raises(ValueError, match="Modelo"):
        PipelineSettings(modelo="u2net")


def test_banda_invalida():
    with pytest.raises(ValueError):
        PipelineSettings(banda_px=0)


def test_ida_y_vuelta_por_diccionario_ignora_claves_desconocidas():
    ajustes = PipelineSettings(modelo="isnet", banda_px=7)
    datos = ajustes.to_dict() | {"campo_viejo": 1}
    assert PipelineSettings.from_dict(datos) == ajustes
