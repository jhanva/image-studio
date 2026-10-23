import pytest

import image_studio.ui.app
from image_studio.__main__ import principal


def test_batch_va_a_la_cli():
    with pytest.raises(SystemExit) as salida:
        principal(["batch", "--help"])
    assert salida.value.code == 0


def test_sin_argumentos_abre_el_editor(monkeypatch):
    llamadas = []
    monkeypatch.setattr(image_studio.ui.app, "run", lambda argv: llamadas.append(argv) or 0)
    assert principal([]) == 0
    assert principal(["foto.png"]) == 0
    assert llamadas == [[], ["foto.png"]]


def test_preparar_y_diagnostico_van_a_la_cli(monkeypatch):
    import image_studio.__main__ as modulo

    llamadas = []
    monkeypatch.setattr(modulo, "cli_main", lambda argv: llamadas.append(argv) or 0)

    def abrir_interfaz(argv):
        raise AssertionError(f"{argv} abrió la interfaz")

    monkeypatch.setattr(image_studio.ui.app, "run", abrir_interfaz)
    assert principal(["preparar"]) == 0
    assert principal(["diagnostico"]) == 0
    assert llamadas == [["preparar"], ["diagnostico"]]
