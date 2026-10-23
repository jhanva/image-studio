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
