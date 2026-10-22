"""ISNet general-use: segmentación rápida."""

from __future__ import annotations

import numpy as np

from image_studio.engines.onnx_segmenter import OnnxSegmenter


class ISNetSegmenter(OnnxSegmenter):
    nombre = "isnet"
    media = (0.5, 0.5, 0.5)
    desviacion = (1.0, 1.0, 1.0)

    def _postprocesar(self, mapa: np.ndarray) -> np.ndarray:
        # Normalización min-max, como en la inferencia original de DIS.
        minimo, maximo = float(mapa.min()), float(mapa.max())
        if maximo - minimo < 1e-6:
            return np.clip(mapa, 0.0, 1.0)
        return (mapa - minimo) / (maximo - minimo)
