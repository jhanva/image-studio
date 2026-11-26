from image_studio.cli import main


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
