"""Ejecutar funciones en el QThreadPool y recibir el resultado en el hilo principal."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Senales(QObject):
    listo = Signal(object)
    fallo = Signal(str)
    avance = Signal(object)


class Tarea(QRunnable):
    def __init__(self, funcion: Callable, *args, con_avance: bool = False):
        super().__init__()
        self.funcion = funcion
        self.args = args
        self.con_avance = con_avance
        self.senales = _Senales()

    def run(self) -> None:
        try:
            if self.con_avance:
                resultado = self.funcion(*self.args, reportar=self.senales.avance.emit)
            else:
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
    al_avanzar: Callable[[object], None] | None = None,
    pool: QThreadPool | None = None,
) -> Tarea:
    """Si se pasa al_avanzar, la función recibe reportar=callable para enviar avances."""
    tarea = Tarea(funcion, *args, con_avance=al_avanzar is not None)
    _activas.add(tarea)
    if al_avanzar is not None:
        tarea.senales.avance.connect(al_avanzar)
    tarea.senales.listo.connect(lambda resultado: (_activas.discard(tarea), al_terminar(resultado)))
    tarea.senales.fallo.connect(lambda mensaje: (_activas.discard(tarea), al_fallar(mensaje)))
    (pool or QThreadPool.globalInstance()).start(tarea)
    return tarea
