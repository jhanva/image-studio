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


def test_resuelve_el_modelo_automatico(tmp_path, escribir_png, removedor_falso):
    from image_studio.engines.hardware import Hardware

    escribir_png(tmp_path / "entrada" / "a.png")
    pedidos = []

    def fabrica(modelo, dispositivo, progreso):
        pedidos.append((modelo, dispositivo))
        return removedor_falso

    codigo = main(
        ["batch", str(tmp_path / "entrada"), str(tmp_path / "salida")],
        crear_removedor=fabrica,
        hardware=Hardware(None, 0, 8192, 4),
    )
    assert codigo == 0
    assert pedidos == [("birefnet_lite", "cpu")]


def test_preparar(capsys):
    assert main(["preparar"]) == 0
    assert "Motor listo" in capsys.readouterr().out


def test_diagnostico_sin_modelos(tmp_path, monkeypatch, capsys):
    from image_studio.engines.hardware import Hardware

    monkeypatch.setenv("IMAGE_STUDIO_MODELS_DIR", str(tmp_path / "vacio"))
    assert main(["diagnostico"], hardware=Hardware(None, 0, 8192, 4)) == 0
    salida = capsys.readouterr().out
    assert "Sin GPU NVIDIA" in salida
    assert "birefnet_lite en CPU" in salida
    assert "no descargado" in salida
