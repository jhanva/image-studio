"""Parámetros de la herramienta de semitonos (spec-semitonos 3.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import Enum

DPI_IMPRESION = 300
Color = tuple[int, int, int]


class KnockoutMode(str, Enum):
    NEGRO = "negro"
    BLANCO = "blanco"
    AUTO = "auto"
    ELEGIDO = "elegido"


class Pattern(str, Enum):
    REDONDO = "redondo"
    DIAMANTE = "diamante"
    ELIPSE = "elipse"
    CUADRADO = "cuadrado"
    LINEA = "linea"
    LINEAS_ONDULADAS = "lineas_onduladas"
    PUNTOS_ONDULADOS = "puntos_ondulados"


class AlphaMode(str, Enum):
    TRAMAR = "tramar"
    CORTAR = "cortar"


_RANGOS: dict[str, tuple[float, float]] = {
    "tolerancia": (0.0, 50.0),
    "encoger_px": (0, 10),
    "lpi": (10.0, 85.0),
    "angulo": (0.0, 180.0),
    "alcance": (1.0, 100.0),
    "peso": (-100.0, 100.0),
    "descartar": (0.0, 20.0),
    "bordes_limpios_px": (0, 10),
    "restaurar": (0.0, 100.0),
}


def _color(valor) -> Color:
    color = tuple(int(c) for c in valor)
    if len(color) != 3 or any(not 0 <= c <= 255 for c in color):
        raise ValueError(f"Color inválido: {valor!r}")
    return color


@dataclass(frozen=True)
class HalftoneSettings:
    """Porcentajes en 0-100. El ancho de impresión no es parte de los ajustes: vive en la sesión."""

    knockout: KnockoutMode = KnockoutMode.NEGRO
    color_elegido: Color = (0, 0, 0)
    quitar_fondo: bool = False
    fondo_interior: bool = False
    colores_borrar: tuple[Color, ...] = ()
    tolerancia: float = 8.0
    encoger_px: int = 0
    lpi: float = 35.0
    angulo: float = 22.5
    ajustar_rejilla: bool = True
    patron: Pattern = Pattern.REDONDO
    alcance: float = 100.0
    peso: float = 0.0
    descartar: float = 3.0
    semitransparencia: AlphaMode = AlphaMode.TRAMAR
    bordes_limpios_px: int = 2
    restaurar: float = 50.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "knockout", KnockoutMode(self.knockout))
        object.__setattr__(self, "patron", Pattern(self.patron))
        object.__setattr__(self, "semitransparencia", AlphaMode(self.semitransparencia))
        object.__setattr__(self, "color_elegido", _color(self.color_elegido))
        object.__setattr__(self, "colores_borrar", tuple(_color(c) for c in self.colores_borrar))
        for nombre, (minimo, maximo) in _RANGOS.items():
            valor = getattr(self, nombre)
            if isinstance(valor, bool) or not minimo <= valor <= maximo:
                raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}")
        for nombre in ("encoger_px", "bordes_limpios_px"):
            if int(getattr(self, nombre)) != getattr(self, nombre):
                raise ValueError(f"{nombre} debe ser entero")
            object.__setattr__(self, nombre, int(getattr(self, nombre)))

    @property
    def gamma(self) -> float:
        """Exponente de la cobertura: peso positivo pone más tinta."""
        return 2.0 ** (-self.peso / 50.0)

    def to_dict(self) -> dict:
        datos = asdict(self)
        for nombre in ("knockout", "patron", "semitransparencia"):
            datos[nombre] = datos[nombre].value
        datos["color_elegido"] = list(self.color_elegido)
        datos["colores_borrar"] = [list(c) for c in self.colores_borrar]
        return datos

    @classmethod
    def from_dict(cls, datos: dict) -> HalftoneSettings:
        """Ignora claves desconocidas; un valor inválido lanza ValueError."""
        conocidos = {f.name for f in fields(cls)}
        try:
            return cls(**{k: v for k, v in datos.items() if k in conocidos})
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
