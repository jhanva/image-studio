"""Pipeline de quitar fondos: segmentar, trimap, matting, ajustes de borde y limpieza de color."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from image_studio.core.image_io import ImageDoc
from image_studio.core.mask_ops import adjust_edge, make_trimap
from image_studio.engines.base import Matter, Segmenter
from image_studio.engines.decontaminate import decontaminate
from image_studio.pipeline.settings import PipelineSettings

LIMITE_INCIERTO = 0.15
COBERTURA_MINIMA = 0.02
COBERTURA_MAXIMA = 0.98


@dataclass
class RemovalResult:
    rgb: np.ndarray
    alpha: np.ndarray
    trimap: np.ndarray | None
    baja_confianza: bool
    motivo_confianza: str
    tiempos: dict[str, float] = field(default_factory=dict)
    dispositivo: str = ""
    """Modelo y dispositivo que se usaron; lo completa RemoverCache."""


def evaluate_confidence(grueso: np.ndarray) -> tuple[bool, str]:
    total = grueso.size
    incierto = np.count_nonzero((grueso > 0.1) & (grueso < 0.9)) / total
    cobertura = np.count_nonzero(grueso >= 0.5) / total
    if incierto > LIMITE_INCIERTO:
        return True, f"borde incierto ({incierto:.0%} de la imagen)"
    if cobertura < COBERTURA_MINIMA:
        return True, f"sujeto muy pequeño ({cobertura:.1%} de la imagen)"
    if cobertura > COBERTURA_MAXIMA:
        return True, f"el sujeto ocupa casi toda la imagen ({cobertura:.1%})"
    return False, ""


class BackgroundRemover:
    def __init__(self, segmentador: Segmenter, matter: Matter | None = None):
        self.segmentador = segmentador
        self.matter = matter

    def run(
        self, doc: ImageDoc, ajustes: PipelineSettings, usar_alfa_existente: bool = False
    ) -> RemovalResult:
        tiempos: dict[str, float] = {}
        inicio = perf_counter()
        if usar_alfa_existente and doc.alpha is not None:
            grueso = doc.alpha.astype(np.float32)
        else:
            grueso = self.segmentador.predict(doc.rgb)
        tiempos["segmentacion"] = perf_counter() - inicio
        baja, motivo = evaluate_confidence(grueso)

        alfa, trimap = grueso, None
        if ajustes.matting:
            if self.matter is None:
                raise ValueError("Los ajustes piden matting pero no hay motor de matting")
            inicio = perf_counter()
            trimap = make_trimap(grueso, ajustes.banda_px)
            alfa = self.matter.refine(doc.rgb, trimap, grueso)
            tiempos["matting"] = perf_counter() - inicio

        alfa = adjust_edge(alfa, ajustes.desplazamiento_px, ajustes.suavizado_px)
        rgb = doc.rgb
        if ajustes.limpieza_color:
            inicio = perf_counter()
            rgb = decontaminate(doc.rgb, alfa)
            tiempos["limpieza_color"] = perf_counter() - inicio
        return RemovalResult(rgb, alfa, trimap, baja, motivo, tiempos)
