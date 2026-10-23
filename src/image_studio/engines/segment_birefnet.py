"""BiRefNet general: segmentación de máxima calidad."""

from __future__ import annotations

import numpy as np

from image_studio.engines.onnx_segmenter import OnnxSegmenter


class BiRefNetSegmenter(OnnxSegmenter):
    nombre = "birefnet"

    def _postprocesar(self, mapa: np.ndarray) -> np.ndarray:
        # El modelo devuelve logits.
        return 1.0 / (1.0 + np.exp(-mapa))
