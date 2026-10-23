"""Calidad sobre el golden set privado (V1, V2 y V3 de la spec)."""

import json
import os
from dataclasses import replace
from pathlib import Path
from statistics import mean

import numpy as np
import pytest
from PIL import Image

from image_studio.core.image_io import FORMATOS_ENTRADA, load_image
from image_studio.core.metrics import iou, sad
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.settings import PRESETS

CARPETA = os.environ.get("IMAGE_STUDIO_GOLDEN_DIR")
pytestmark = [
    pytest.mark.golden,
    pytest.mark.model,
    pytest.mark.skipif(not CARPETA, reason="IMAGE_STUDIO_GOLDEN_DIR no definido"),
]
TOLERANCIA = 0.02


def _casos(categoria: str) -> list[tuple[Path, Path]]:
    casos = []
    for imagen in sorted((Path(CARPETA) / categoria).iterdir()):
        if imagen.name.endswith(".mask.png") or imagen.suffix.lower() not in FORMATOS_ENTRADA:
            continue
        mascara = imagen.with_name(imagen.stem + ".mask.png")
        if mascara.exists():
            casos.append((imagen, mascara))
    return casos


def _mascara(ruta: Path) -> np.ndarray:
    with Image.open(ruta) as imagen:
        return np.asarray(imagen.convert("L"), np.float32) / 255.0


def _evaluar(removedor, categoria, ajustes) -> list[dict]:
    filas = []
    for imagen, mascara in _casos(categoria):
        referencia = _mascara(mascara)
        alfa = removedor.run(load_image(imagen), ajustes).alpha
        filas.append({"nombre": imagen.name, "iou": iou(alfa, referencia), "sad": sad(alfa, referencia)})
    return filas


@pytest.fixture(scope="module")
def resultados():
    removedor = build_remover("birefnet")
    persona = PRESETS["persona"]
    return {
        "producto": _evaluar(removedor, "producto", PRESETS["producto"]),
        "persona": _evaluar(removedor, "persona", persona),
        "persona_sin_matting": _evaluar(removedor, "persona", replace(persona, matting=False)),
    }


def test_v1_calidad_en_producto(resultados):
    filas = resultados["producto"]
    assert len(filas) >= 8, "El golden set de producto necesita al menos 8 imágenes"
    assert mean(f["iou"] for f in filas) >= 0.97, filas


def test_v2_matting_mejora_personas(resultados):
    con, sin = resultados["persona"], resultados["persona_sin_matting"]
    assert len(con) >= 6, "El golden set de persona necesita al menos 6 imágenes"
    assert mean(f["sad"] for f in con) <= mean(f["sad"] for f in sin)
    mejoras = sum(c["sad"] < s["sad"] for c, s in zip(con, sin))
    assert mejoras / len(con) >= 0.7, list(zip(con, sin))


def test_v3_sin_regresiones(resultados):
    actual = {
        "producto_iou": mean(f["iou"] for f in resultados["producto"]),
        "persona_sad": mean(f["sad"] for f in resultados["persona"]),
    }
    ruta = Path(CARPETA) / "baseline.json"
    if os.environ.get("IMAGE_STUDIO_GOLDEN_UPDATE") == "1" or not ruta.exists():
        ruta.write_text(json.dumps(actual, indent=2), encoding="utf-8")
        pytest.skip(f"Baseline guardado en {ruta}")
    base = json.loads(ruta.read_text(encoding="utf-8"))
    assert actual["producto_iou"] >= base["producto_iou"] * (1 - TOLERANCIA), (actual, base)
    assert actual["persona_sad"] <= base["persona_sad"] * (1 + TOLERANCIA), (actual, base)
