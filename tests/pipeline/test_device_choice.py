import pytest

from image_studio.engines.hardware import Hardware
from image_studio.pipeline.device_choice import choose

RTX_8GB = Hardware("NVIDIA GeForce RTX 3050", 8192, 16384, 6)
GTX_4GB = Hardware("NVIDIA GeForce GTX 1650", 4096, 8192, 4)
SIN_GPU = Hardware(None, 0, 8192, 4)


def test_automatico_con_gpu_grande():
    eleccion = choose("auto", RTX_8GB)
    assert (eleccion.modelo, eleccion.dispositivo) == ("birefnet", "auto")
    assert "GPU" in eleccion.descripcion


def test_automatico_sin_gpu_usa_el_liviano_en_cpu():
    eleccion = choose("auto", SIN_GPU)
    assert (eleccion.modelo, eleccion.dispositivo) == ("birefnet_lite", "cpu")
    assert "sin GPU NVIDIA" in eleccion.descripcion


def test_gpu_pequena_va_a_cpu_salvo_isnet():
    assert choose("birefnet", GTX_4GB).dispositivo == "cpu"
    assert choose("isnet", GTX_4GB).dispositivo == "auto"
    assert "4096 MB" in choose("birefnet_lite", GTX_4GB).descripcion


def test_modelo_desconocido():
    with pytest.raises(ValueError):
        choose("u2net", RTX_8GB)
