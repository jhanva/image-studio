"""Interfaces de los motores de IA."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Segmenter(Protocol):
    nombre: str

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        """Alfa grueso HxW float32 en [0, 1] para una imagen HxWx3 uint8."""
        ...


class Matter(Protocol):
    nombre: str

    def refine(self, rgb: np.ndarray, trimap: np.ndarray, grueso: np.ndarray) -> np.ndarray:
        """Alfa refinado HxW float32 en [0, 1]; solo cambia la zona desconocida del trimap."""
        ...
