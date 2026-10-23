import threading

from image_studio.workers.tasks import ejecutar


def test_devuelve_el_resultado_en_el_hilo_principal(qtbot):
    recibidos, hilos = [], []

    def sumar(a, b):
        hilos.append(threading.current_thread())
        return a + b

    ejecutar(sumar, 2, 3, al_terminar=recibidos.append, al_fallar=recibidos.append)
    qtbot.waitUntil(lambda: recibidos == [5])
    assert hilos[0] is not threading.main_thread()


def test_reporta_el_error(qtbot):
    errores = []

    def fallar():
        raise ValueError("malo")

    ejecutar(fallar, al_terminar=errores.append, al_fallar=errores.append)
    qtbot.waitUntil(lambda: bool(errores))
    assert errores == ["ValueError: malo"]


def test_reporta_avance_antes_del_resultado(qtbot):
    eventos = []

    def contar(hasta, reportar):
        for i in range(1, hasta + 1):
            reportar(i)
        return "listo"

    ejecutar(
        contar,
        3,
        al_terminar=eventos.append,
        al_fallar=eventos.append,
        al_avanzar=eventos.append,
    )
    qtbot.waitUntil(lambda: "listo" in eventos)
    assert eventos == [1, 2, 3, "listo"]
