"""Ajustes del pipeline de quitar fondos y presets incluidos."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

MODELOS_SEGMENTACION = ("auto", "birefnet", "birefnet_lite", "isnet")


@dataclass(frozen=True)
class PipelineSettings:
    modelo: str = "auto"
    matting: bool = True
    limpieza_color: bool = True
    banda_px: int = 10
    desplazamiento_px: int = 0
    suavizado_px: float = 0.0

    def __post_init__(self) -> None:
        if self.modelo not in MODELOS_SEGMENTACION:
            raise ValueError(f"Modelo no soportado: {self.modelo}")
        if self.banda_px < 1:
            raise ValueError("banda_px debe ser >= 1")
        if self.suavizado_px < 0:
            raise ValueError("suavizado_px debe ser >= 0")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, datos: dict) -> PipelineSettings:
        conocidos = {campo.name for campo in fields(cls)}
        return cls(**{clave: valor for clave, valor in datos.items() if clave in conocidos})


PRESETS = {
    # Termos y pocillos: sin matting para que los reflejos no queden semitransparentes.
    "producto": PipelineSettings(matting=False, limpieza_color=True),
    # Pelo y pelaje: matting en una banda ancha.
    "persona": PipelineSettings(matting=True, limpieza_color=True, banda_px=10),
}
