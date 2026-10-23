import argparse

import pytest

from image_studio.cli import color_hex, main


def _fabrica(removedor):
    return lambda modelo, dispositivo, progreso: removedor


def test_lote_con_fondo_blanco_en_jpg(tmp_path, escribir_png, removedor_falso):
    escribir_png(tmp_path / "entrada" / "a.png")
    codigo = main(
        ["batch", str(tmp_path / "entrada"), str(tmp_path / "salida"), "--fondo", "blanco", "--formato", "jpg"],
        crear_removedor=_fabrica(removedor_falso),
    )
    assert codigo == 0
    assert (tmp_path / "salida" / "a.jpg").exists()
    assert (tmp_path / "salida" / "informe.csv").exists()


def test_carpeta_inexistente_devuelve_2(tmp_path, removedor_falso, capsys):
    codigo = main(
        ["batch", str(tmp_path / "no"), str(tmp_path / "salida")], crear_removedor=_fabrica(removedor_falso)
    )
    assert codigo == 2
    assert "no existe" in capsys.readouterr().err


def test_errores_devuelven_1(tmp_path, removedor_falso):
    (tmp_path / "entrada").mkdir()
    (tmp_path / "entrada" / "roto.png").write_bytes(b"x")
    codigo = main(
        ["batch", str(tmp_path / "entrada"), str(tmp_path / "salida")], crear_removedor=_fabrica(removedor_falso)
    )
    assert codigo == 1


def test_color_hex():
    assert color_hex("#00FF80") == (0, 255, 128)
    with pytest.raises(argparse.ArgumentTypeError):
        color_hex("verde")
