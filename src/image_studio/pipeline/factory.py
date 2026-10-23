"""Construcción del removedor de fondos a partir de los modelos instalados."""

from __future__ import annotations

from image_studio.engines.matting_classic import ClassicMatter
from image_studio.engines.model_manager import MODELOS, Progreso, create_session, ensure_model
from image_studio.engines.segment_birefnet import BiRefNetLiteSegmenter, BiRefNetSegmenter
from image_studio.engines.segment_isnet import ISNetSegmenter
from image_studio.pipeline.remove_bg import BackgroundRemover

_SEGMENTADORES = {"birefnet": BiRefNetSegmenter, "birefnet_lite": BiRefNetLiteSegmenter, "isnet": ISNetSegmenter}


def build_remover(
    modelo: str, dispositivo: str = "auto", progreso: Progreso | None = None
) -> BackgroundRemover:
    if modelo not in _SEGMENTADORES:
        raise ValueError(f"Modelo no soportado: {modelo}")
    ruta = ensure_model(MODELOS[modelo], progreso)
    sesion = create_session(ruta, dispositivo)
    return BackgroundRemover(_SEGMENTADORES[modelo](sesion), ClassicMatter())
