"""Métricas de calidad de máscaras para el golden set."""

from __future__ import annotations

import numpy as np


def _validar(pred: np.ndarray, ref: np.ndarray) -> None:
    if pred.shape != ref.shape:
        raise ValueError(f"Formas distintas: {pred.shape} y {ref.shape}")


def iou(pred: np.ndarray, ref: np.ndarray, umbral: float = 0.5) -> float:
    _validar(pred, ref)
    p, r = pred >= umbral, ref >= umbral
    union = np.logical_or(p, r).sum()
    return 1.0 if union == 0 else float(np.logical_and(p, r).sum() / union)


def sad(pred: np.ndarray, ref: np.ndarray) -> float:
    """Suma de diferencias absolutas de alfa, en miles (convención de los benchmarks de matting)."""
    _validar(pred, ref)
    return float(np.abs(pred.astype(np.float64) - ref).sum() / 1000.0)


def mse(pred: np.ndarray, ref: np.ndarray) -> float:
    _validar(pred, ref)
    return float(np.mean((pred.astype(np.float64) - ref) ** 2))
