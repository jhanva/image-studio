import hashlib

import pytest

from image_studio.engines.model_manager import (
    MODELOS,
    ModelError,
    ModelSpec,
    available_providers,
    ensure_model,
)


@pytest.fixture(autouse=True)
def carpeta_modelos(tmp_path, monkeypatch):
    carpeta = tmp_path / "modelos"
    monkeypatch.setenv("IMAGE_STUDIO_MODELS_DIR", str(carpeta))
    return carpeta


def _spec(origen, sha256=None):
    datos = origen.read_bytes()
    return ModelSpec(
        "prueba", "prueba.onnx", origen.as_uri(), sha256 or hashlib.sha256(datos).hexdigest(), len(datos)
    )


def test_descarga_y_verifica(tmp_path, carpeta_modelos):
    origen = tmp_path / "origen.onnx"
    origen.write_bytes(b"x" * 3_000_000)
    avances = []
    ruta = ensure_model(_spec(origen), progreso=lambda leidos, total: avances.append((leidos, total)))
    assert ruta == carpeta_modelos / "prueba.onnx"
    assert ruta.read_bytes() == origen.read_bytes()
    assert avances[-1] == (3_000_000, 3_000_000)


def test_hash_invalido_no_deja_archivos(tmp_path, carpeta_modelos):
    origen = tmp_path / "origen.onnx"
    origen.write_bytes(b"x" * 10)
    with pytest.raises(ModelError, match="Hash"):
        ensure_model(_spec(origen, sha256="0" * 64))
    assert not any(carpeta_modelos.iterdir())


def test_no_descarga_si_ya_existe(tmp_path, carpeta_modelos):
    carpeta_modelos.mkdir()
    (carpeta_modelos / "prueba.onnx").write_bytes(b"y" * 10)
    spec = ModelSpec("prueba", "prueba.onnx", (tmp_path / "no-existe").as_uri(), "0" * 64, 10)
    assert ensure_model(spec).read_bytes() == b"y" * 10


def test_origen_inaccesible(tmp_path):
    spec = ModelSpec("prueba", "prueba.onnx", (tmp_path / "no-existe").as_uri(), "0" * 64, 5)
    with pytest.raises(ModelError, match="No se pudo descargar"):
        ensure_model(spec)


def test_modelos_registrados():
    assert set(MODELOS) == {"birefnet", "birefnet_lite", "isnet"}
    for spec in MODELOS.values():
        assert len(spec.sha256) == 64
        assert spec.url.startswith("https://")


def test_proveedores_terminan_en_cpu():
    assert available_providers()[-1] == "CPUExecutionProvider"
