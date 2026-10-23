import threading
import time
from pathlib import Path

import numpy as np

from image_studio.core.image_io import ImageDoc
from image_studio.engines.hardware import Hardware
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.settings import PipelineSettings


def test_crea_una_vez_por_modelo_y_dispositivo():
    llamadas = []
    cache = RemoverCache(lambda modelo, dispositivo, progreso: llamadas.append((modelo, dispositivo)) or object())
    a = cache.get("birefnet")
    assert cache.get("birefnet") is a
    cache.get("isnet")
    cache.get("birefnet", "cpu")
    assert llamadas == [("birefnet", "auto"), ("isnet", "auto"), ("birefnet", "cpu")]


def test_hilos_simultaneos_cargan_el_modelo_una_sola_vez():
    llamadas = []

    def crear(modelo, dispositivo, progreso):
        llamadas.append(modelo)
        time.sleep(0.05)
        return object()

    cache = RemoverCache(crear)
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(cache.get("birefnet"))) for _ in range(5)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert llamadas == ["birefnet"]
    assert len({id(r) for r in resultados}) == 1


RTX_8GB = Hardware("RTX", 8192, 16384, 6)
SIN_GPU = Hardware(None, 0, 8192, 4)


class Removedor:
    def __init__(self, modelo, dispositivo, fallar=False):
        self.modelo, self.dispositivo, self.fallar = modelo, dispositivo, fallar

    def run(self, doc, ajustes, usar_alfa_existente=False):
        if self.fallar:
            raise RuntimeError("CUDA out of memory")
        alfa = np.ones(doc.rgb.shape[:2], np.float32)
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.0})


def _doc():
    return ImageDoc(Path("x.png"), np.zeros((8, 8, 3), np.uint8), None, None, None)


def test_automatico_usa_la_eleccion_del_equipo():
    creados = []
    cache = RemoverCache(lambda m, d, p: creados.append((m, d)) or Removedor(m, d), hardware=SIN_GPU)
    resultado = cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet_lite", "cpu")]
    assert "birefnet_lite en CPU" in resultado.dispositivo


def test_si_la_gpu_falla_repite_en_cpu_y_lo_recuerda():
    creados = []

    def crear(modelo, dispositivo, progreso):
        creados.append((modelo, dispositivo))
        return Removedor(modelo, dispositivo, fallar=dispositivo == "auto")

    cache = RemoverCache(crear, hardware=RTX_8GB)
    resultado = cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet", "auto"), ("birefnet", "cpu")]
    assert "la GPU falló" in resultado.dispositivo
    cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet", "auto"), ("birefnet", "cpu")]


def test_detecta_el_equipo_una_sola_vez():
    cache = RemoverCache(lambda m, d, p: Removedor(m, d))
    assert cache.hardware is cache.hardware
