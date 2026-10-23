"""Base común de los segmentadores ONNX: preproceso, inferencia y escalado al tamaño original."""

from __future__ import annotations

import cv2
import numpy as np


class OnnxSegmenter:
    nombre = "onnx"
    lado = 1024
    media = (0.485, 0.456, 0.406)
    desviacion = (0.229, 0.224, 0.225)

    def __init__(self, sesion):
        self._sesion = sesion
        self._entrada = sesion.get_inputs()[0].name

    @property
    def proveedor(self) -> str | None:
        """Proveedor que quedó activo; ONNX Runtime cae a CPU sin error si CUDA no está disponible."""
        obtener = getattr(self._sesion, "get_providers", None)
        return obtener()[0] if obtener else None

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        alto, ancho = rgb.shape[:2]
        salida = self._sesion.run(None, {self._entrada: self._preparar(rgb)})[0]
        mapa = self._postprocesar(salida[0, 0].astype(np.float32))
        alfa = cv2.resize(mapa, (ancho, alto), interpolation=cv2.INTER_LINEAR)
        return np.clip(alfa, 0.0, 1.0)

    def _preparar(self, rgb: np.ndarray) -> np.ndarray:
        reduce = rgb.shape[0] > self.lado or rgb.shape[1] > self.lado
        interpolacion = cv2.INTER_AREA if reduce else cv2.INTER_CUBIC
        x = cv2.resize(rgb, (self.lado, self.lado), interpolation=interpolacion)
        x = x.astype(np.float32) / 255.0
        x = (x - np.array(self.media, np.float32)) / np.array(self.desviacion, np.float32)
        return np.ascontiguousarray(x.transpose(2, 0, 1)[None])

    def _postprocesar(self, mapa: np.ndarray) -> np.ndarray:
        raise NotImplementedError
