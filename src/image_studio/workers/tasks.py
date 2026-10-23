"""Ejecutar funciones en el QThreadPool y recibir el resultado en el hilo principal."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Senales(QObject):
    listo = Signal(object)
    fallo = Signal(str)


class Tarea(QRunnable):
    def __init__(self, funcion: Callable, *args):
        super().__init__()
        self.funcion = funcion
        self.args = args
        self.senales = _Senales()

    def run(self) -> None:
        try:
            resultado = self.funcion(*self.args)
        except Exception as exc:  # el error se muestra en la interfaz, no se pierde en el hilo
            self.senales.fallo.emit(f"{type(exc).__name__}: {exc}")
            return
        self.senales.listo.emit(resultado)


# Referencias vivas hasta que la tarea avisa; sin ellas Python puede destruir las señales antes.
_activas: set[Tarea] = set()


def ejecutar(
    funcion: Callable,
    *args,
    al_terminar: Callable[[object], None],
    al_fallar: Callable[[str], None],
    pool: QThreadPool | None = None,
) -> Tarea:
    tarea = Tarea(funcion, *args)
    _activas.add(tarea)
    tarea.senales.listo.connect(lambda resultado: (_activas.discard(tarea), al_terminar(resultado)))
    tarea.senales.fallo.connect(lambda mensaje: (_activas.discard(tarea), al_fallar(mensaje)))
    (pool or QThreadPool.globalInstance()).start(tarea)
    return tarea
