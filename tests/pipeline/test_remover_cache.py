import threading
import time

from image_studio.pipeline.remover_cache import RemoverCache


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
