import json

import pytest

from image_studio.core.halftone.settings import AlphaMode, HalftoneSettings, KnockoutMode, Pattern


def test_valores_por_defecto():
    a = HalftoneSettings()
    assert a.knockout is KnockoutMode.NEGRO
    assert (a.lpi, a.angulo, a.descartar, a.bordes_limpios_px, a.restaurar) == (35.0, 22.5, 3.0, 2, 50.0)
    assert a.patron is Pattern.REDONDO and a.semitransparencia is AlphaMode.TRAMAR
    assert a.ajustar_rejilla


@pytest.mark.parametrize(
    "cambio",
    [{"lpi": 5}, {"angulo": 181}, {"alcance": 0}, {"peso": 101}, {"descartar": 21},
     {"bordes_limpios_px": 11}, {"encoger_px": 1.5}, {"color_elegido": (0, 0, 256)},
     {"patron": "estrella"}, {"tolerancia": True}],
)
def test_rangos_invalidos(cambio):
    with pytest.raises(ValueError):
        HalftoneSettings(**cambio)


def test_gamma():
    assert HalftoneSettings(peso=0).gamma == 1.0
    assert HalftoneSettings(peso=100).gamma == 0.25
    assert HalftoneSettings(peso=-100).gamma == 4.0


def test_ida_y_vuelta_por_json():
    a = HalftoneSettings(
        knockout="elegido", color_elegido=(10, 20, 30), colores_borrar=[(1, 2, 3)],
        patron=Pattern.LINEAS_ONDULADAS, semitransparencia="cortar", lpi=45,
    )
    assert HalftoneSettings.from_dict(json.loads(json.dumps(a.to_dict()))) == a


def test_from_dict_ignora_claves_desconocidas_y_rechaza_invalidas():
    assert HalftoneSettings.from_dict({"lpi": 40, "otra": 1}).lpi == 40
    with pytest.raises(ValueError):
        HalftoneSettings.from_dict({"lpi": 500})
