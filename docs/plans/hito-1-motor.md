# Plan de implementación - Hito 1: motor y CLI de quitar fondos

Spec: [../spec.md](../spec.md). Flujo: [../repo-workflow.md](../repo-workflow.md).
Rama: `feature/hito-1-motor` desde `develop`. Un commit por tarea; PR a `develop` (squash) al final.

## Objetivo del hito

Pipeline completo sin interfaz: cargar imagen, segmentar (BiRefNet o ISNet), trimap, matting
clásico, limpieza de color, ajustes de borde, exportación y procesamiento por lotes desde la
línea de comandos con informe CSV. Verificable con imágenes reales antes de construir la UI.

## Hitos siguientes (se planifican al cerrar este)

- **Hito 2 - Editor:** ventana PySide6, lienzo con zoom, tablero y antes/después, pinceles
  Conservar/Borrar/Refinar borde, historial por tiles (V6, V8).
- **Hito 3 - Suite:** interfaz `Tool`, panel de lotes, presets propios guardados, diálogo de
  exportación; ViTMatte si el riesgo R1 queda resuelto.

## Datos verificados en el equipo objetivo (2026-10-22)

| Dato | Valor |
|---|---|
| Python | 3.14.7 |
| Driver NVIDIA / VRAM | 617.42 / 8 GB, `CUDAExecutionProvider` disponible con `onnxruntime-gpu[cuda,cudnn]==1.31.0` |
| BiRefNet | entrada `input_image` [1,3,1024,1024], una salida `output_image` [1,1,1024,1024] en logits |
| ISNet | entrada `input_image` [1,3,1024,1024], 12 salidas; la primera es el mapa en [0,1] |
| BiRefNet GPU | 1.5 s por imagen con `enable_mem_pattern = False`; 22 s con el valor por defecto (desborda VRAM) |
| Matting clásico | borde de un sujeto en 4000x3000, bloques de 256 px, banda 10 px: 2.4 s; error en banda 0.026 frente a 0.074 del alfa grueso |
| Limpieza de color | `estimate_foreground_ml` en 4000x3000 completo: 2.3 s; por bloques de borde, una fracción |
| SHA-256 BiRefNet | `58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c` (972666916 bytes) |
| SHA-256 ISNet | `60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a` (178648008 bytes) |

Los MD5 de ambos archivos coinciden con los publicados en `rembg`
(`7a35a0141cbbc80de11d9c9a28f52697` y `fc16ebd8b0c10d971d3513d564d01e29`).

## Mapa de archivos

- Modificar: `docs/spec.md` (Python 3.14, estructura, hitos, ajuste de memoria ONNX)
- Crear: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`
- Crear: `src/image_studio/__init__.py`, `__main__.py`, `cli.py`
- Crear: `src/image_studio/core/{__init__,image_io,mask_ops,export,metrics}.py`
- Crear: `src/image_studio/engines/{__init__,base,model_manager,onnx_segmenter,segment_birefnet,segment_isnet,matting_classic,decontaminate}.py`
- Crear: `src/image_studio/pipeline/{__init__,settings,remove_bg,factory,batch}.py`
- Crear: `scripts/benchmark.py`
- Crear: `tests/conftest.py`, `tests/test_package.py`, `tests/test_boundaries.py`, `tests/test_cli.py`
- Crear: `tests/core/test_{image_io,mask_ops,export,metrics}.py`
- Crear: `tests/engines/test_{model_manager,segmenters,segmenters_real,matting_classic,decontaminate}.py`
- Crear: `tests/pipeline/test_{settings,remove_bg,factory,batch}.py`
- Crear: `tests/golden/test_golden.py`
- Modificar: `README.md` (uso de la CLI)

Convenciones: módulos, clases y funciones públicas en inglés (como la spec: `ImageDoc`,
`load_image`); campos de ajustes, variables y textos en español. Todo comando se ejecuta desde
la raíz del repo en PowerShell.

---

## Fase A - Base

### Tarea 1: actualizar la spec

**Archivos:** modificar `docs/spec.md`

Sin test (documental). Cambios exactos:

1. En la tabla 3.1, reemplazar `| Lenguaje | Python 3.12 |` por `| Lenguaje | Python 3.14 |`.
2. En la tabla 3.1, reemplazar la fila de Inferencia por:
   `| Inferencia | ONNX Runtime: `onnxruntime-gpu[cuda,cudnn]` (CUDA) con respaldo a CPU; sesiones con `enable_mem_pattern = False` (con el patrón de memoria BiRefNet desborda 8 GB de VRAM y pasa de 1.5 s a 22 s) |`
3. En la tabla 3.2, fila de matting de borde, cambiar la columna Uso a:
   `Pelo, pelaje, semitransparencias. Se integra cuando se resuelva R1; mientras tanto se usa el matting clásico`
4. En el árbol 3.4, agregar bajo `core/` la línea
   `      metrics.py          # IoU, SAD y MSE para el golden set`,
   bajo `engines/` antes de `segment_birefnet.py` la línea
   `      onnx_segmenter.py   # base común: preproceso, inferencia y escalado`,
   y bajo `pipeline/` las líneas
   `      settings.py         # PipelineSettings y presets` y
   `      factory.py          # construye el removedor desde los modelos`.
5. Agregar al final de la sección 3.7:
   `- Entregas por hitos: Hito 1 motor y CLI; Hito 2 editor; Hito 3 suite (lotes en UI, presets propios, exportación en UI). Planes en `docs/plans/`.`

**Verificar:**
```powershell
Select-String -Path docs\spec.md -Pattern "Python 3.14","enable_mem_pattern","onnx_segmenter.py","factory.py","Entregas por hitos"
```
Esperado: 5 coincidencias.

**Commit:**
```powershell
git add docs/spec.md
git commit -m "docs(spec): actualizar a python 3.14 y separar entregas por hitos"
```

### Tarea 2: paquete, dependencias y entorno

**Archivos:** crear `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`,
`src/image_studio/__init__.py`, `src/image_studio/{core,engines,pipeline}/__init__.py` (vacíos),
`tests/test_package.py`

**Paso 1 - Test que falla** (`tests/test_package.py`):
```python
from importlib.metadata import version

import image_studio


def test_version_viene_de_pyproject():
    assert image_studio.__version__ == version("image-studio") == "0.1.0"
```

**Paso 2 - Recrear el entorno y verificar que falla:**
```powershell
Remove-Item -Recurse -Force .venv
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -q --upgrade pip pytest==9.1.1
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_package.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio'`.

**Paso 3 - Implementar:**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "image-studio"
version = "0.1.0"
description = "Suite de escritorio Windows para manipular imágenes"
requires-python = ">=3.14"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
markers = [
    "model: requiere los modelos ONNX descargados",
    "golden: requiere IMAGE_STUDIO_GOLDEN_DIR",
]
```

`requirements.txt`:
```text
# Dependencias de la app. Instalar con el Python de .venv.
numpy==2.5.4
opencv-python-headless==5.0.0.93
pillow==13.0.0
pillow-heif==1.8.1
PyMatting==1.1.16
onnxruntime-gpu[cuda,cudnn]==1.31.0
```

`requirements-dev.txt`:
```text
-r requirements.txt
pytest==9.1.1
```

`src/image_studio/__init__.py`:
```python
"""Image Studio: suite de escritorio para manipular imágenes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("image-studio")
except PackageNotFoundError:
    __version__ = "0.0.0"
```

Crear vacíos `src/image_studio/core/__init__.py`, `src/image_studio/engines/__init__.py` y
`src/image_studio/pipeline/__init__.py`.

```powershell
.\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -q -e . --no-deps
```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_package.py -q
```
Esperado: `1 passed`.

**Commit:**
```powershell
git add pyproject.toml requirements.txt requirements-dev.txt src tests/test_package.py
git commit -m "build(repo): crear paquete image_studio y dependencias fijadas"
```

### Tarea 3: test de fronteras sin Qt (V10)

**Archivos:** crear `tests/test_boundaries.py`

**Paso 1 - Test:**
```python
"""V10: core, engines y pipeline no pueden importar Qt."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "image_studio"
CAPAS_SIN_QT = ("core", "engines", "pipeline")
PROHIBIDOS = {"PySide6", "shiboken6"}


def _archivos() -> list[Path]:
    return sorted(p for capa in CAPAS_SIN_QT for p in (SRC / capa).rglob("*.py"))


def _modulos_importados(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    modulos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.append(nodo.module)
    return modulos


def test_hay_archivos_que_revisar():
    assert _archivos()


@pytest.mark.parametrize("ruta", _archivos(), ids=lambda p: p.relative_to(SRC).as_posix())
def test_capa_no_importa_qt(ruta):
    prohibidos = [m for m in _modulos_importados(ruta) if m.split(".")[0] in PROHIBIDOS]
    assert not prohibidos, f"{ruta.name} importa {prohibidos}"
```

**Paso 2 - Verificar el test contra un caso malo:** agregar temporalmente
`import PySide6` a `src/image_studio/core/__init__.py`.
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_boundaries.py -q
```
Esperado: `1 failed` en `core/__init__.py importa ['PySide6']`. Quitar la línea.

**Paso 3 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add tests/test_boundaries.py
git commit -m "test(repo): impedir imports de qt en core, engines y pipeline"
```

---

## Fase B - Core

### Tarea 4: cargar imágenes normalizadas

**Archivos:** crear `src/image_studio/core/image_io.py`, `tests/conftest.py`,
`tests/core/test_image_io.py`

**Paso 1 - Tests que fallan.**

`tests/conftest.py`:
```python
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def escribir_png():
    """Crea un PNG RGB sintético y devuelve su ruta."""

    def _escribir(ruta: Path, ancho: int = 8, alto: int = 8, color=(200, 40, 30)) -> Path:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((alto, ancho, 3), color, np.uint8)).save(ruta)
        return ruta

    return _escribir
```

`tests/core/test_image_io.py`:
```python
import numpy as np
import pytest
from PIL import Image

from image_studio.core.image_io import ImageLoadError, load_image


def test_carga_png_rgb(escribir_png, tmp_path):
    doc = load_image(escribir_png(tmp_path / "a.png", ancho=20, alto=10))
    assert doc.rgb.shape == (10, 20, 3)
    assert doc.rgb.dtype == np.uint8
    assert doc.alpha is None
    assert doc.size == (20, 10)


def test_conserva_alfa_existente(tmp_path):
    ruta = tmp_path / "alfa.png"
    Image.new("RGBA", (4, 4), (10, 20, 30, 128)).save(ruta)
    doc = load_image(ruta)
    assert doc.alpha.dtype == np.float32
    assert doc.alpha[0, 0] == pytest.approx(128 / 255)
    assert tuple(doc.rgb[0, 0]) == (10, 20, 30)


def test_aplica_orientacion_exif(tmp_path):
    ruta = tmp_path / "rotada.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (20, 10)).save(ruta, exif=exif)
    assert load_image(ruta).rgb.shape == (20, 10, 3)


def test_ruta_con_tildes_y_enie(escribir_png, tmp_path):
    doc = load_image(escribir_png(tmp_path / "canción ñandú.png"))
    assert doc.path.name == "canción ñandú.png"


def test_convierte_cmyk(tmp_path):
    ruta = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (8, 8), (0, 0, 0, 0)).save(ruta)
    assert load_image(ruta).rgb.shape == (8, 8, 3)


def test_convierte_png_de_16_bits(tmp_path):
    ruta = tmp_path / "gris16.png"
    Image.new("I;16", (4, 4), 65535).save(ruta)
    doc = load_image(ruta)
    assert doc.rgb.shape == (4, 4, 3)
    assert (doc.rgb == 255).all()


def test_lee_dpi(tmp_path):
    ruta = tmp_path / "dpi.png"
    Image.new("RGB", (4, 4)).save(ruta, dpi=(300, 300))
    assert load_image(ruta).dpi == pytest.approx((300, 300), abs=0.01)


def test_archivo_corrupto(tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"no es una imagen")
    with pytest.raises(ImageLoadError, match="roto.png"):
        load_image(ruta)


def test_formato_no_soportado(tmp_path):
    with pytest.raises(ImageLoadError, match="Formato no soportado"):
        load_image(tmp_path / "animacion.gif")
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_image_io.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.image_io'`.

**Paso 3 - Implementar** `src/image_studio/core/image_io.py`:
```python
"""Carga de imágenes normalizadas a RGB de 8 bits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()

FORMATOS_ENTRADA = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)
_MODOS_16_BITS = ("I;16", "I;16B", "I;16L", "I")


class ImageLoadError(Exception):
    """La imagen no se pudo leer o su formato no está soportado."""


@dataclass
class ImageDoc:
    path: Path
    rgb: np.ndarray
    """HxWx3 uint8."""
    alpha: np.ndarray | None
    """HxW float32 en [0, 1] si el archivo traía transparencia."""
    dpi: tuple[float, float] | None
    icc_profile: bytes | None

    @property
    def size(self) -> tuple[int, int]:
        alto, ancho = self.rgb.shape[:2]
        return ancho, alto


def load_image(path: str | Path) -> ImageDoc:
    path = Path(path)
    if path.suffix.lower() not in FORMATOS_ENTRADA:
        raise ImageLoadError(f"Formato no soportado: {path.suffix or '(sin extensión)'}")
    try:
        with Image.open(path) as imagen:
            imagen.load()
            info = dict(imagen.info)
            orientada = ImageOps.exif_transpose(imagen)
            rgb, alpha = _a_rgb8(orientada)
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ImageLoadError(f"No se pudo leer {path.name}: {exc}") from exc
    return ImageDoc(
        path=path,
        rgb=rgb,
        alpha=alpha,
        dpi=_dpi(info.get("dpi")),
        icc_profile=info.get("icc_profile"),
    )


def _a_rgb8(imagen: Image.Image) -> tuple[np.ndarray, np.ndarray | None]:
    if imagen.mode in _MODOS_16_BITS:
        valores = np.array(imagen, dtype=np.float64)
        gris = np.clip(valores / 257.0 + 0.5, 0, 255).astype(np.uint8)
        return np.repeat(gris[..., None], 3, axis=2), None
    tiene_alfa = imagen.mode in ("RGBA", "LA", "PA") or (
        imagen.mode == "P" and "transparency" in imagen.info
    )
    if tiene_alfa:
        rgba = np.array(imagen.convert("RGBA"))
        return np.ascontiguousarray(rgba[..., :3]), rgba[..., 3].astype(np.float32) / 255.0
    return np.array(imagen.convert("RGB")), None


def _dpi(valor) -> tuple[float, float] | None:
    if not valor:
        return None
    return float(valor[0]), float(valor[1])
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `9 passed`.

**Commit:**
```powershell
git add src/image_studio/core/image_io.py tests/conftest.py tests/core/test_image_io.py
git commit -m "feat(core): cargar imagenes normalizadas a rgb de 8 bits"
```

### Tarea 5: trimap y ajustes de borde

**Archivos:** crear `src/image_studio/core/mask_ops.py`, `tests/core/test_mask_ops.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest

from image_studio.core.mask_ops import (
    DESCONOCIDO,
    FONDO,
    FRENTE,
    adjust_edge,
    content_bbox,
    make_trimap,
)


def _cuadro(n: int = 100) -> np.ndarray:
    alfa = np.zeros((n, n), np.float32)
    alfa[30:70, 30:70] = 1.0
    return alfa


def test_trimap_marca_frente_fondo_y_banda():
    trimap = make_trimap(_cuadro(), banda_px=5)
    assert trimap.dtype == np.uint8
    assert trimap[50, 50] == FRENTE
    assert trimap[0, 0] == FONDO
    assert trimap[30, 50] == DESCONOCIDO
    assert trimap[27, 50] == DESCONOCIDO
    assert trimap[20, 50] == FONDO


def test_trimap_marca_valores_inciertos_como_desconocido():
    alfa = np.zeros((50, 50), np.float32)
    alfa[:10, :10] = 0.3
    assert (make_trimap(alfa, banda_px=2)[:10, :10] == DESCONOCIDO).all()


def test_trimap_rechaza_banda_cero():
    with pytest.raises(ValueError):
        make_trimap(_cuadro(), banda_px=0)


def test_desplazamiento_positivo_agranda_y_negativo_achica():
    alfa = _cuadro()
    area = (alfa >= 0.5).sum()
    assert (adjust_edge(alfa, desplazamiento_px=3) >= 0.5).sum() > area
    assert (adjust_edge(alfa, desplazamiento_px=-3) >= 0.5).sum() < area


def test_suavizado_crea_valores_intermedios_en_rango():
    salida = adjust_edge(_cuadro(), suavizado_px=2.0)
    assert ((salida > 0.05) & (salida < 0.95)).any()
    assert salida.min() >= 0.0 and salida.max() <= 1.0
    assert salida.dtype == np.float32


def test_sin_ajustes_devuelve_copia_igual():
    alfa = _cuadro()
    salida = adjust_edge(alfa)
    assert np.array_equal(salida, alfa) and salida is not alfa


def test_caja_de_contenido():
    assert content_bbox(_cuadro()) == (30, 30, 70, 70)
    assert content_bbox(np.zeros((10, 10), np.float32)) is None
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_mask_ops.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.mask_ops'`.

**Paso 3 - Implementar** `src/image_studio/core/mask_ops.py`:
```python
"""Operaciones sobre máscaras alfa float32 en [0, 1]."""

from __future__ import annotations

import cv2
import numpy as np

FONDO, DESCONOCIDO, FRENTE = 0, 128, 255


def _nucleo(radio: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))


def make_trimap(alpha: np.ndarray, banda_px: int, umbral: float = 0.5) -> np.ndarray:
    """Frente y fondo seguros, con una banda desconocida de banda_px a cada lado del borde."""
    if banda_px < 1:
        raise ValueError("banda_px debe ser >= 1")
    binaria = (alpha >= umbral).astype(np.uint8)
    nucleo = _nucleo(banda_px)
    trimap = np.full(alpha.shape, DESCONOCIDO, np.uint8)
    trimap[cv2.erode(binaria, nucleo) == 1] = FRENTE
    trimap[cv2.dilate(binaria, nucleo) == 0] = FONDO
    trimap[(alpha > 0.05) & (alpha < 0.95)] = DESCONOCIDO
    return trimap


def adjust_edge(
    alpha: np.ndarray, desplazamiento_px: int = 0, suavizado_px: float = 0.0
) -> np.ndarray:
    """Expande (positivo) o contrae (negativo) el borde y luego lo suaviza."""
    salida = alpha.astype(np.float32, copy=True)
    if desplazamiento_px > 0:
        salida = cv2.dilate(salida, _nucleo(desplazamiento_px))
    elif desplazamiento_px < 0:
        salida = cv2.erode(salida, _nucleo(-desplazamiento_px))
    if suavizado_px > 0:
        salida = cv2.GaussianBlur(salida, (0, 0), sigmaX=suavizado_px)
    return np.clip(salida, 0.0, 1.0)


def content_bbox(alpha: np.ndarray, umbral: float = 0.01) -> tuple[int, int, int, int] | None:
    """Caja (x0, y0, x1, y1) con x1 e y1 exclusivos, o None si la máscara está vacía."""
    filas, columnas = np.nonzero(alpha > umbral)
    if filas.size == 0:
        return None
    return int(columnas.min()), int(filas.min()), int(columnas.max()) + 1, int(filas.max()) + 1
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `7 passed`.

**Commit:**
```powershell
git add src/image_studio/core/mask_ops.py tests/core/test_mask_ops.py
git commit -m "feat(core): generar trimap y ajustar bordes de mascara"
```

### Tarea 6: componer y guardar la exportación (V7, V12)

**Archivos:** crear `src/image_studio/core/export.py`, `tests/core/test_export.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest
from PIL import Image

from image_studio.core.export import ExportSettings, Fondo, compose, save


def _rojo_con_cuadro(n: int = 10):
    rgb = np.zeros((n, n, 3), np.uint8)
    rgb[...] = (255, 0, 0)
    alfa = np.zeros((n, n), np.float32)
    alfa[2:5, 2:5] = 1.0
    return rgb, alfa


def test_transparente_agrega_canal_alfa():
    salida = compose(*_rojo_con_cuadro(), ExportSettings())
    assert salida.shape == (10, 10, 4)
    assert salida[3, 3, 3] == 255 and salida[0, 0, 3] == 0


def test_fondo_blanco():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(fondo=Fondo.BLANCO))
    assert salida.shape == (10, 10, 3)
    assert tuple(salida[0, 0]) == (255, 255, 255)
    assert tuple(salida[3, 3]) == (255, 0, 0)


def test_fondo_de_color():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(fondo=Fondo.COLOR, color=(0, 128, 0)))
    assert tuple(salida[0, 0]) == (0, 128, 0)


def test_jpg_transparente_usa_blanco():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(formato="jpg"))
    assert salida.shape == (10, 10, 3)
    assert tuple(salida[0, 0]) == (255, 255, 255)


def test_recorta_al_contenido_con_margen():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(recortar=True, margen_px=1))
    assert salida.shape == (5, 5, 4)


def test_recortar_mascara_vacia_no_recorta():
    rgb, _ = _rojo_con_cuadro()
    salida = compose(rgb, np.zeros((10, 10), np.float32), ExportSettings(recortar=True))
    assert salida.shape == (10, 10, 4)


def test_png_conserva_mascara_pixel_a_pixel(tmp_path):
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
    alfa = rng.random((32, 32)).astype(np.float32)
    ruta = save(compose(rgb, alfa, ExportSettings()), tmp_path / "v7.png", ExportSettings())
    with Image.open(ruta) as imagen:
        guardado = np.array(imagen)
    esperado = np.clip(alfa * 255.0 + 0.5, 0, 255).astype(np.uint8)
    assert np.array_equal(guardado[..., 3], esperado)
    assert np.array_equal(guardado[..., :3], rgb)


def test_cambia_la_extension_segun_formato(tmp_path):
    ruta = save(compose(*_rojo_con_cuadro(), ExportSettings()), tmp_path / "a.jpg", ExportSettings())
    assert ruta.name == "a.png" and ruta.exists()


def test_ruta_con_tildes_y_dpi(tmp_path):
    ajustes = ExportSettings(dpi=300)
    ruta = save(compose(*_rojo_con_cuadro(), ajustes), tmp_path / "salida ñ" / "canción.png", ajustes)
    with Image.open(ruta) as imagen:
        assert imagen.info["dpi"] == pytest.approx((300, 300), abs=0.01)


def test_formato_invalido():
    with pytest.raises(ValueError):
        ExportSettings(formato="gif")
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_export.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.export'`.

**Paso 3 - Implementar** `src/image_studio/core/export.py`:
```python
"""Composición del recorte con su fondo y escritura del archivo final."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image

from image_studio.core.mask_ops import content_bbox

FORMATOS_SALIDA = {"png": "PNG", "webp": "WEBP", "jpg": "JPEG"}
BLANCO = (255, 255, 255)


class Fondo(str, Enum):
    TRANSPARENTE = "transparente"
    BLANCO = "blanco"
    COLOR = "color"


@dataclass(frozen=True)
class ExportSettings:
    formato: str = "png"
    fondo: Fondo = Fondo.TRANSPARENTE
    color: tuple[int, int, int] = BLANCO
    recortar: bool = False
    margen_px: int = 0
    dpi: int | None = None

    def __post_init__(self) -> None:
        if self.formato not in FORMATOS_SALIDA:
            raise ValueError(f"Formato de salida no soportado: {self.formato}")
        if self.margen_px < 0:
            raise ValueError("margen_px debe ser >= 0")


def compose(rgb: np.ndarray, alpha: np.ndarray, ajustes: ExportSettings) -> np.ndarray:
    """Devuelve HxWx4 uint8 si el fondo es transparente, o HxWx3 uint8 con el fondo aplicado."""
    if ajustes.recortar:
        rgb, alpha = _recortar(rgb, alpha, ajustes.margen_px)
    fondo = ajustes.fondo
    if fondo is Fondo.TRANSPARENTE and ajustes.formato == "jpg":
        fondo = Fondo.BLANCO
    if fondo is Fondo.TRANSPARENTE:
        alfa8 = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return np.dstack([rgb, alfa8])
    color = np.array(BLANCO if fondo is Fondo.BLANCO else ajustes.color, np.float32)
    peso = alpha[..., None].astype(np.float32)
    mezcla = rgb.astype(np.float32) * peso + color * (1.0 - peso)
    return np.clip(mezcla + 0.5, 0, 255).astype(np.uint8)


def save(
    imagen: np.ndarray, path: str | Path, ajustes: ExportSettings, icc_profile: bytes | None = None
) -> Path:
    destino = Path(path).with_suffix("." + ajustes.formato)
    destino.parent.mkdir(parents=True, exist_ok=True)
    opciones: dict = {}
    if ajustes.dpi:
        opciones["dpi"] = (ajustes.dpi, ajustes.dpi)
    if icc_profile:
        opciones["icc_profile"] = icc_profile
    if ajustes.formato == "webp":
        opciones["lossless"] = True
    if ajustes.formato == "jpg":
        opciones.update(quality=95, subsampling=0)
    Image.fromarray(imagen).save(destino, FORMATOS_SALIDA[ajustes.formato], **opciones)
    return destino


def _recortar(rgb: np.ndarray, alpha: np.ndarray, margen: int):
    caja = content_bbox(alpha)
    if caja is None:
        return rgb, alpha
    alto, ancho = alpha.shape
    x0, y0, x1, y1 = caja
    x0, y0 = max(0, x0 - margen), max(0, y0 - margen)
    x1, y1 = min(ancho, x1 + margen), min(alto, y1 + margen)
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `10 passed`.

**Commit:**
```powershell
git add src/image_studio/core/export.py tests/core/test_export.py
git commit -m "feat(core): componer fondo y guardar png, webp y jpg"
```

### Tarea 7: métricas de calidad

**Archivos:** crear `src/image_studio/core/metrics.py`, `tests/core/test_metrics.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest

from image_studio.core.metrics import iou, mse, sad

UNOS = np.ones((10, 10), np.float32)
CEROS = np.zeros((10, 10), np.float32)


def test_iou():
    assert iou(UNOS, UNOS) == 1.0
    assert iou(UNOS, CEROS) == 0.0
    assert iou(CEROS, CEROS) == 1.0


def test_sad_en_miles():
    assert sad(UNOS, CEROS) == pytest.approx(0.1)


def test_mse():
    assert mse(UNOS * 0.5, CEROS) == pytest.approx(0.25)


def test_formas_distintas():
    with pytest.raises(ValueError):
        iou(UNOS, np.ones((5, 5), np.float32))
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_metrics.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.metrics'`.

**Paso 3 - Implementar** `src/image_studio/core/metrics.py`:
```python
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
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/core/metrics.py tests/core/test_metrics.py
git commit -m "feat(core): agregar metricas iou, sad y mse"
```

---

## Fase C - Motores

### Tarea 8: interfaces y gestor de modelos

**Archivos:** crear `src/image_studio/engines/base.py`, `src/image_studio/engines/model_manager.py`,
`tests/engines/test_model_manager.py`

**Paso 1 - Tests que fallan:**
```python
import hashlib

import pytest

from image_studio.engines.model_manager import (
    MODELOS,
    ModelError,
    ModelSpec,
    available_providers,
    ensure_model,
)


@pytest.fixture(autouse=True)
def carpeta_modelos(tmp_path, monkeypatch):
    carpeta = tmp_path / "modelos"
    monkeypatch.setenv("IMAGE_STUDIO_MODELS_DIR", str(carpeta))
    return carpeta


def _spec(origen, sha256=None):
    datos = origen.read_bytes()
    return ModelSpec(
        "prueba", "prueba.onnx", origen.as_uri(), sha256 or hashlib.sha256(datos).hexdigest(), len(datos)
    )


def test_descarga_y_verifica(tmp_path, carpeta_modelos):
    origen = tmp_path / "origen.onnx"
    origen.write_bytes(b"x" * 3_000_000)
    avances = []
    ruta = ensure_model(_spec(origen), progreso=lambda leidos, total: avances.append((leidos, total)))
    assert ruta == carpeta_modelos / "prueba.onnx"
    assert ruta.read_bytes() == origen.read_bytes()
    assert avances[-1] == (3_000_000, 3_000_000)


def test_hash_invalido_no_deja_archivos(tmp_path, carpeta_modelos):
    origen = tmp_path / "origen.onnx"
    origen.write_bytes(b"x" * 10)
    with pytest.raises(ModelError, match="Hash"):
        ensure_model(_spec(origen, sha256="0" * 64))
    assert not any(carpeta_modelos.iterdir())


def test_no_descarga_si_ya_existe(tmp_path, carpeta_modelos):
    carpeta_modelos.mkdir()
    (carpeta_modelos / "prueba.onnx").write_bytes(b"y" * 10)
    spec = ModelSpec("prueba", "prueba.onnx", (tmp_path / "no-existe").as_uri(), "0" * 64, 10)
    assert ensure_model(spec).read_bytes() == b"y" * 10


def test_origen_inaccesible(tmp_path):
    spec = ModelSpec("prueba", "prueba.onnx", (tmp_path / "no-existe").as_uri(), "0" * 64, 5)
    with pytest.raises(ModelError, match="No se pudo descargar"):
        ensure_model(spec)


def test_modelos_registrados():
    assert set(MODELOS) == {"birefnet", "isnet"}
    for spec in MODELOS.values():
        assert len(spec.sha256) == 64
        assert spec.url.startswith("https://")


def test_proveedores_terminan_en_cpu():
    assert available_providers()[-1] == "CPUExecutionProvider"
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_model_manager.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.model_manager'`.

**Paso 3 - Implementar.**

`src/image_studio/engines/base.py`:
```python
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
```

`src/image_studio/engines/model_manager.py`:
```python
"""Descarga, verificación y carga de modelos ONNX."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

Progreso = Callable[[int, int], None]
_BASE_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"


@dataclass(frozen=True)
class ModelSpec:
    nombre: str
    archivo: str
    url: str
    sha256: str
    tamano: int


MODELOS = {
    "birefnet": ModelSpec(
        "birefnet",
        "BiRefNet-general-epoch_244.onnx",
        _BASE_URL + "BiRefNet-general-epoch_244.onnx",
        "58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c",
        972666916,
    ),
    "isnet": ModelSpec(
        "isnet",
        "isnet-general-use.onnx",
        _BASE_URL + "isnet-general-use.onnx",
        "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
        178648008,
    ),
}


class ModelError(Exception):
    """El modelo no se pudo descargar, verificar o cargar."""


def models_dir() -> Path:
    personalizado = os.environ.get("IMAGE_STUDIO_MODELS_DIR")
    if personalizado:
        return Path(personalizado)
    return Path(os.environ["LOCALAPPDATA"]) / "ImageStudio" / "models"


def ensure_model(spec: ModelSpec, progreso: Progreso | None = None) -> Path:
    """Devuelve la ruta local del modelo; lo descarga y verifica si falta."""
    destino = models_dir() / spec.archivo
    if destino.exists():
        if destino.stat().st_size == spec.tamano:
            return destino
        destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    try:
        _descargar(spec.url, parcial, spec.tamano, progreso)
        if _sha256(parcial) != spec.sha256:
            raise ModelError(f"Hash inválido para {spec.archivo}")
        parcial.replace(destino)
    except ModelError:
        parcial.unlink(missing_ok=True)
        raise
    except OSError as exc:
        parcial.unlink(missing_ok=True)
        raise ModelError(f"No se pudo descargar {spec.archivo}: {exc}") from exc
    return destino


def _descargar(url: str, destino: Path, tamano: int, progreso: Progreso | None) -> None:
    with urllib.request.urlopen(url, timeout=60) as respuesta, open(destino, "wb") as archivo:
        total = int(respuesta.headers.get("Content-Length") or tamano)
        leidos = 0
        while bloque := respuesta.read(1 << 20):
            archivo.write(bloque)
            leidos += len(bloque)
            if progreso:
                progreso(leidos, total)


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while bloque := archivo.read(1 << 20):
            resumen.update(bloque)
    return resumen.hexdigest()


@cache
def available_providers() -> list[str]:
    """CUDA primero si está disponible y sus DLL cargan; CPU siempre al final."""
    import onnxruntime as ort

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return ["CPUExecutionProvider"]
    try:
        ort.preload_dlls()
    except Exception:  # DLL de CUDA/cuDNN ausentes o incompatibles: se usa CPU
        return ["CPUExecutionProvider"]
    return ["CUDAExecutionProvider", "CPUExecutionProvider"]


def create_session(ruta: Path, dispositivo: str = "auto"):
    """Sesión ONNX Runtime; dispositivo es "auto" o "cpu"."""
    import onnxruntime as ort

    opciones = ort.SessionOptions()
    # Con el patrón de memoria, BiRefNet desborda 8 GB de VRAM y pasa de 1.5 s a 22 s.
    opciones.enable_mem_pattern = False
    opciones.log_severity_level = 3
    proveedores = ["CPUExecutionProvider"] if dispositivo == "cpu" else available_providers()
    try:
        return ort.InferenceSession(str(ruta), opciones, providers=proveedores)
    except Exception as exc:
        raise ModelError(f"No se pudo cargar {Path(ruta).name}: {exc}") from exc
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/engines/base.py src/image_studio/engines/model_manager.py tests/engines/test_model_manager.py
git commit -m "feat(engines): descargar, verificar y cargar modelos onnx"
```

### Tarea 9: segmentador base y BiRefNet

**Archivos:** crear `src/image_studio/engines/onnx_segmenter.py`,
`src/image_studio/engines/segment_birefnet.py`, `tests/engines/test_segmenters.py`

**Paso 1 - Tests que fallan** (`tests/engines/test_segmenters.py`):
```python
from types import SimpleNamespace

import numpy as np

from image_studio.engines.segment_birefnet import BiRefNetSegmenter


class SesionFalsa:
    def __init__(self, salida: np.ndarray):
        self.salida = salida
        self.recibido = None

    def get_inputs(self):
        return [SimpleNamespace(name="input_image")]

    def run(self, _salidas, entradas):
        self.recibido = entradas["input_image"]
        return [self.salida]


def test_birefnet_normaliza_y_devuelve_tamano_original():
    sesion = SesionFalsa(np.zeros((1, 1, 1024, 1024), np.float32))
    rgb = np.empty((200, 300, 3), np.uint8)
    rgb[...] = (124, 116, 104)
    alfa = BiRefNetSegmenter(sesion).predict(rgb)
    assert sesion.recibido.shape == (1, 3, 1024, 1024)
    assert sesion.recibido.dtype == np.float32
    assert np.abs(sesion.recibido).max() < 0.01
    assert alfa.shape == (200, 300)
    assert np.allclose(alfa, 0.5)


def test_birefnet_aplica_sigmoide():
    logits = np.full((1, 1, 1024, 1024), -20.0, np.float32)
    logits[..., :512] = 20.0
    alfa = BiRefNetSegmenter(SesionFalsa(logits)).predict(np.zeros((64, 64, 3), np.uint8))
    assert alfa[:, :20].min() > 0.99
    assert alfa[:, 44:].max() < 0.01
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_segmenters.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.segment_birefnet'`.

**Paso 3 - Implementar.**

`src/image_studio/engines/onnx_segmenter.py`:
```python
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
```

`src/image_studio/engines/segment_birefnet.py`:
```python
"""BiRefNet general: segmentación de máxima calidad."""

from __future__ import annotations

import numpy as np

from image_studio.engines.onnx_segmenter import OnnxSegmenter


class BiRefNetSegmenter(OnnxSegmenter):
    nombre = "birefnet"

    def _postprocesar(self, mapa: np.ndarray) -> np.ndarray:
        # El modelo devuelve logits.
        return 1.0 / (1.0 + np.exp(-mapa))
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `2 passed`.

**Commit:**
```powershell
git add src/image_studio/engines/onnx_segmenter.py src/image_studio/engines/segment_birefnet.py tests/engines/test_segmenters.py
git commit -m "feat(engines): segmentar con birefnet sobre base onnx comun"
```

### Tarea 10: ISNet y prueba con modelos reales

**Archivos:** crear `src/image_studio/engines/segment_isnet.py`,
`tests/engines/test_segmenters_real.py`; modificar `tests/engines/test_segmenters.py`

**Paso 1 - Tests que fallan.** En `tests/engines/test_segmenters.py`, agregar junto a los
imports del inicio `from image_studio.engines.segment_isnet import ISNetSegmenter` y al final:
```python
def test_isnet_normaliza_min_max():
    mapa = np.full((1, 1, 1024, 1024), 2.0, np.float32)
    mapa[..., :512] = 4.0
    alfa = ISNetSegmenter(SesionFalsa(mapa)).predict(np.zeros((64, 64, 3), np.uint8))
    assert alfa.max() == 1.0 and alfa.min() == 0.0


def test_isnet_usa_media_0_5():
    sesion = SesionFalsa(np.zeros((1, 1, 1024, 1024), np.float32))
    rgb = np.full((32, 32, 3), 128, np.uint8)
    ISNetSegmenter(sesion).predict(rgb)
    assert np.abs(sesion.recibido).max() < 0.01
```

`tests/engines/test_segmenters_real.py`:
```python
"""Segmentación real con los modelos descargados (marca model)."""

import numpy as np
import pytest

from image_studio.core.metrics import iou
from image_studio.engines.model_manager import MODELOS, create_session, models_dir
from image_studio.engines.segment_birefnet import BiRefNetSegmenter
from image_studio.engines.segment_isnet import ISNetSegmenter

pytestmark = pytest.mark.model
CLASES = {"birefnet": BiRefNetSegmenter, "isnet": ISNetSegmenter}


@pytest.fixture(scope="module", params=sorted(CLASES))
def segmentador(request):
    ruta = models_dir() / MODELOS[request.param].archivo
    if not ruta.exists():
        pytest.skip(f"Modelo {request.param} no descargado")
    return CLASES[request.param](create_session(ruta))


def test_segmenta_disco_sobre_fondo_liso(segmentador):
    alto, ancho = 600, 800
    filas, columnas = np.mgrid[:alto, :ancho]
    disco = np.hypot(filas - 300, columnas - 400) <= 180
    rgb = np.full((alto, ancho, 3), 235, np.uint8)
    rgb[disco] = (200, 40, 30)
    alfa = segmentador.predict(rgb)
    assert iou(alfa, disco.astype(np.float32)) >= 0.9
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_segmenters.py tests/engines/test_segmenters_real.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.segment_isnet'`.

**Paso 3 - Implementar** `src/image_studio/engines/segment_isnet.py`:
```python
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
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed` (4 unitarias y 2 reales;
si los modelos no están en `%LOCALAPPDATA%\ImageStudio\models`, las 2 reales salen `skipped`).

**Commit:**
```powershell
git add src/image_studio/engines/segment_isnet.py tests/engines/test_segmenters.py tests/engines/test_segmenters_real.py
git commit -m "feat(engines): segmentar con isnet y probar ambos modelos reales"
```

### Tarea 11: matting clásico por bloques

**Archivos:** crear `src/image_studio/engines/matting_classic.py`,
`tests/engines/test_matting_classic.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE, make_trimap
from image_studio.engines.matting_classic import ClassicMatter


def _borde_suave(n: int = 160):
    filas, columnas = np.mgrid[:n, :n]
    radio = np.hypot(filas - n / 2, columnas - n / 2)
    real = np.clip((50 - radio) / 4 + 0.5, 0, 1).astype(np.float32)
    rng = np.random.default_rng(0)
    frente = np.array([200, 60, 40], np.float32)
    fondo = rng.uniform(150, 230, (n, n, 3)).astype(np.float32)
    rgb = (real[..., None] * frente + (1 - real[..., None]) * fondo).astype(np.uint8)
    return rgb, real, (real >= 0.5).astype(np.float32)


def test_mejora_el_borde_frente_al_alfa_grueso():
    rgb, real, grueso = _borde_suave()
    trimap = make_trimap(grueso, banda_px=6)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    banda = trimap == DESCONOCIDO
    assert np.abs(alfa - real)[banda].mean() < 0.5 * np.abs(grueso - real)[banda].mean()


def test_respeta_zonas_seguras():
    rgb, _, grueso = _borde_suave()
    trimap = make_trimap(grueso, banda_px=6)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    assert (alfa[trimap == FRENTE] == 1.0).all()
    assert (alfa[trimap == FONDO] == 0.0).all()
    assert alfa.dtype == np.float32


def test_bloque_sin_frente_conserva_el_grueso():
    rgb = np.full((64, 64, 3), 128, np.uint8)
    trimap = np.full((64, 64), DESCONOCIDO, np.uint8)
    trimap[:, :10] = FONDO
    grueso = np.full((64, 64), 0.3, np.float32)
    alfa = ClassicMatter(tile=64, margen=16).refine(rgb, trimap, grueso)
    assert np.allclose(alfa[:, 20:], 0.3)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_matting_classic.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.matting_classic'`.

**Paso 3 - Implementar** `src/image_studio/engines/matting_classic.py`:
```python
"""Matting clásico (closed-form de pymatting) por bloques sobre la banda desconocida."""

from __future__ import annotations

import numpy as np
from pymatting import estimate_alpha_cf

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE


class ClassicMatter:
    nombre = "clasico"

    def __init__(self, tile: int = 256, margen: int = 32):
        self.tile = tile
        self.margen = margen

    def refine(self, rgb: np.ndarray, trimap: np.ndarray, grueso: np.ndarray) -> np.ndarray:
        alfa = grueso.astype(np.float32, copy=True)
        alfa[trimap == FRENTE] = 1.0
        alfa[trimap == FONDO] = 0.0
        imagen = rgb.astype(np.float64) / 255.0
        trimap_01 = trimap.astype(np.float64) / 255.0
        alto, ancho = trimap.shape
        for y in range(0, alto, self.tile):
            for x in range(0, ancho, self.tile):
                nucleo = trimap[y : y + self.tile, x : x + self.tile]
                desconocido = nucleo == DESCONOCIDO
                if not desconocido.any():
                    continue
                y0, x0 = max(0, y - self.margen), max(0, x - self.margen)
                y1 = min(alto, y + self.tile + self.margen)
                x1 = min(ancho, x + self.tile + self.margen)
                recorte = trimap_01[y0:y1, x0:x1]
                # Sin frente y fondo seguros el sistema no tiene restricciones: se deja el grueso.
                if not ((recorte == 0.0).any() and (recorte == 1.0).any()):
                    continue
                estimado = estimate_alpha_cf(imagen[y0:y1, x0:x1], recorte)
                alto_n, ancho_n = nucleo.shape
                bloque = estimado[y - y0 : y - y0 + alto_n, x - x0 : x - x0 + ancho_n]
                destino = alfa[y : y + alto_n, x : x + ancho_n]
                destino[desconocido] = bloque[desconocido]
        return np.clip(alfa, 0.0, 1.0)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/engines/matting_classic.py tests/engines/test_matting_classic.py
git commit -m "feat(engines): refinar borde con matting clasico por bloques"
```

### Tarea 12: limpieza de color en bordes

**Archivos:** crear `src/image_studio/engines/decontaminate.py`,
`tests/engines/test_decontaminate.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np

from image_studio.engines.decontaminate import decontaminate


def _degradado(n: int = 64):
    alfa = np.zeros((n, n), np.float32)
    alfa[:, :28] = 1.0
    alfa[:, 28:36] = np.linspace(1.0, 0.0, 8, dtype=np.float32)
    frente, fondo = np.array([220, 30, 30], np.float32), np.array([30, 30, 220], np.float32)
    rgb = (alfa[..., None] * frente + (1 - alfa[..., None]) * fondo).astype(np.uint8)
    return rgb, alfa


def test_recupera_el_color_del_frente_en_el_borde():
    rgb, alfa = _degradado()
    limpio = decontaminate(rgb, alfa)
    borde = (alfa > 0.2) & (alfa < 0.8)
    assert limpio[borde][:, 0].mean() > rgb[borde][:, 0].mean() + 30
    assert np.array_equal(limpio[alfa >= 0.99], rgb[alfa >= 0.99])


def test_sin_borde_devuelve_copia():
    rgb = np.full((16, 16, 3), 90, np.uint8)
    alfa = np.ones((16, 16), np.float32)
    limpio = decontaminate(rgb, alfa)
    assert np.array_equal(limpio, rgb) and limpio is not rgb
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_decontaminate.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.decontaminate'`.

**Paso 3 - Implementar** `src/image_studio/engines/decontaminate.py`:
```python
"""Estimación del color real del frente en píxeles de borde (quita el halo del fondo)."""

from __future__ import annotations

import numpy as np
from pymatting import estimate_foreground_ml


def decontaminate(
    rgb: np.ndarray, alpha: np.ndarray, tile: int = 256, margen: int = 16
) -> np.ndarray:
    salida = rgb.copy()
    borde = (alpha > 0.01) & (alpha < 0.99)
    if not borde.any():
        return salida
    imagen = rgb.astype(np.float64) / 255.0
    alfa = alpha.astype(np.float64)
    alto, ancho = alpha.shape
    for y in range(0, alto, tile):
        for x in range(0, ancho, tile):
            nucleo = borde[y : y + tile, x : x + tile]
            if not nucleo.any():
                continue
            y0, x0 = max(0, y - margen), max(0, x - margen)
            y1, x1 = min(alto, y + tile + margen), min(ancho, x + tile + margen)
            frente = estimate_foreground_ml(imagen[y0:y1, x0:x1], alfa[y0:y1, x0:x1])
            alto_n, ancho_n = nucleo.shape
            bloque = frente[y - y0 : y - y0 + alto_n, x - x0 : x - x0 + ancho_n]
            bloque8 = np.clip(bloque * 255.0 + 0.5, 0, 255).astype(np.uint8)
            destino = salida[y : y + alto_n, x : x + ancho_n]
            destino[nucleo] = bloque8[nucleo]
    return salida
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `2 passed`.

**Commit:**
```powershell
git add src/image_studio/engines/decontaminate.py tests/engines/test_decontaminate.py
git commit -m "feat(engines): limpiar color del fondo en bordes"
```

---

## Fase D - Pipeline y CLI

### Tarea 13: ajustes y presets

**Archivos:** crear `src/image_studio/pipeline/settings.py`, `tests/pipeline/test_settings.py`

**Paso 1 - Tests que fallan:**
```python
import pytest

from image_studio.pipeline.settings import PRESETS, PipelineSettings


def test_presets_incluidos():
    assert set(PRESETS) == {"producto", "persona"}
    assert PRESETS["producto"].matting is False
    assert PRESETS["persona"].matting is True


def test_modelo_invalido():
    with pytest.raises(ValueError, match="Modelo"):
        PipelineSettings(modelo="u2net")


def test_banda_invalida():
    with pytest.raises(ValueError):
        PipelineSettings(banda_px=0)


def test_ida_y_vuelta_por_diccionario_ignora_claves_desconocidas():
    ajustes = PipelineSettings(modelo="isnet", banda_px=7)
    datos = ajustes.to_dict() | {"campo_viejo": 1}
    assert PipelineSettings.from_dict(datos) == ajustes
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_settings.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.settings'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/settings.py`:
```python
"""Ajustes del pipeline de quitar fondos y presets incluidos."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

MODELOS_SEGMENTACION = ("birefnet", "isnet")


@dataclass(frozen=True)
class PipelineSettings:
    modelo: str = "birefnet"
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
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/settings.py tests/pipeline/test_settings.py
git commit -m "feat(pipeline): definir ajustes y presets producto y persona"
```

### Tarea 14: orquestar quitar fondo

**Archivos:** crear `src/image_studio/pipeline/remove_bg.py`, `tests/pipeline/test_remove_bg.py`

**Paso 1 - Tests que fallan:**
```python
from pathlib import Path

import numpy as np
import pytest

from image_studio.core.image_io import ImageDoc
from image_studio.pipeline.remove_bg import BackgroundRemover, evaluate_confidence
from image_studio.pipeline.settings import PipelineSettings

SIN_EXTRAS = PipelineSettings(matting=False, limpieza_color=False)


class SegmentadorFalso:
    nombre = "falso"

    def __init__(self, alfa):
        self.alfa = alfa
        self.llamadas = 0

    def predict(self, rgb):
        self.llamadas += 1
        return self.alfa.copy()


class MatterFalso:
    nombre = "falso"

    def __init__(self):
        self.trimap = None

    def refine(self, rgb, trimap, grueso):
        self.trimap = trimap
        return grueso * 0.9


def _cuadro(n: int = 100):
    alfa = np.zeros((n, n), np.float32)
    alfa[30:70, 30:70] = 1.0
    return alfa


def _doc(alfa_archivo=None, n: int = 100):
    return ImageDoc(Path("x.png"), np.full((n, n, 3), 128, np.uint8), alfa_archivo, None, None)


def test_sin_matting_devuelve_el_alfa_del_segmentador():
    matter = MatterFalso()
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro()), matter).run(_doc(), SIN_EXTRAS)
    assert matter.trimap is None and resultado.trimap is None
    assert np.array_equal(resultado.alpha, _cuadro())
    assert "segmentacion" in resultado.tiempos


def test_con_matting_usa_trimap_y_motor():
    matter = MatterFalso()
    ajustes = PipelineSettings(matting=True, limpieza_color=False, banda_px=4)
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro()), matter).run(_doc(), ajustes)
    assert matter.trimap is not None and resultado.trimap is matter.trimap
    assert np.allclose(resultado.alpha, _cuadro() * 0.9)


def test_matting_sin_motor_falla():
    with pytest.raises(ValueError, match="matting"):
        BackgroundRemover(SegmentadorFalso(_cuadro())).run(_doc(), PipelineSettings(limpieza_color=False))


def test_usa_alfa_existente_sin_segmentar():
    segmentador = SegmentadorFalso(_cuadro())
    resultado = BackgroundRemover(segmentador).run(_doc(alfa_archivo=_cuadro() * 0.5), SIN_EXTRAS, usar_alfa_existente=True)
    assert segmentador.llamadas == 0
    assert np.allclose(resultado.alpha, _cuadro() * 0.5)


def test_limpieza_de_color_conserva_forma():
    ajustes = PipelineSettings(matting=False, limpieza_color=True, suavizado_px=2.0)
    resultado = BackgroundRemover(SegmentadorFalso(_cuadro())).run(_doc(), ajustes)
    assert resultado.rgb.shape == (100, 100, 3) and resultado.rgb.dtype == np.uint8


def test_confianza():
    assert evaluate_confidence(_cuadro()) == (False, "")
    baja, motivo = evaluate_confidence(np.zeros((100, 100), np.float32))
    assert baja and "pequeño" in motivo
    baja, motivo = evaluate_confidence(np.ones((100, 100), np.float32))
    assert baja and "casi toda" in motivo
    baja, motivo = evaluate_confidence(np.full((100, 100), 0.5, np.float32))
    assert baja and "incierto" in motivo
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_remove_bg.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.remove_bg'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/remove_bg.py`:
```python
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
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/remove_bg.py tests/pipeline/test_remove_bg.py
git commit -m "feat(pipeline): orquestar segmentacion, matting y limpieza de color"
```

### Tarea 15: construir el removedor desde los modelos

**Archivos:** crear `src/image_studio/pipeline/factory.py`, `tests/pipeline/test_factory.py`

**Paso 1 - Tests que fallan:**
```python
import pytest

from image_studio.engines.matting_classic import ClassicMatter
from image_studio.engines.model_manager import MODELOS, models_dir
from image_studio.pipeline.factory import build_remover


def test_modelo_desconocido():
    with pytest.raises(ValueError, match="Modelo"):
        build_remover("u2net")


@pytest.mark.model
@pytest.mark.parametrize("modelo", sorted(MODELOS))
def test_construye_con_modelo_descargado(modelo):
    if not (models_dir() / MODELOS[modelo].archivo).exists():
        pytest.skip(f"Modelo {modelo} no descargado")
    removedor = build_remover(modelo, dispositivo="cpu")
    assert removedor.segmentador.nombre == modelo
    assert isinstance(removedor.matter, ClassicMatter)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_factory.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.factory'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/factory.py`:
```python
"""Construcción del removedor de fondos a partir de los modelos instalados."""

from __future__ import annotations

from image_studio.engines.matting_classic import ClassicMatter
from image_studio.engines.model_manager import MODELOS, Progreso, create_session, ensure_model
from image_studio.engines.segment_birefnet import BiRefNetSegmenter
from image_studio.engines.segment_isnet import ISNetSegmenter
from image_studio.pipeline.remove_bg import BackgroundRemover

_SEGMENTADORES = {"birefnet": BiRefNetSegmenter, "isnet": ISNetSegmenter}


def build_remover(
    modelo: str, dispositivo: str = "auto", progreso: Progreso | None = None
) -> BackgroundRemover:
    if modelo not in _SEGMENTADORES:
        raise ValueError(f"Modelo no soportado: {modelo}")
    ruta = ensure_model(MODELOS[modelo], progreso)
    sesion = create_session(ruta, dispositivo)
    return BackgroundRemover(_SEGMENTADORES[modelo](sesion), ClassicMatter())
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/factory.py tests/pipeline/test_factory.py
git commit -m "feat(pipeline): construir removedor desde los modelos instalados"
```

### Tarea 16: procesamiento por lotes con informe (V9, V11, V12)

**Archivos:** crear `src/image_studio/pipeline/batch.py`, `tests/pipeline/test_batch.py`;
modificar `tests/conftest.py`

**Paso 1 - Tests que fallan.** En `tests/conftest.py`, agregar junto a los imports del inicio
`from image_studio.pipeline.remove_bg import RemovalResult` y al final:
```python
class RemovedorFalso:
    """Devuelve un alfa casi completo sin cargar modelos."""

    def run(self, doc, ajustes, usar_alfa_existente=False):
        alfa = np.ones(doc.rgb.shape[:2], np.float32)
        alfa[0, 0] = 0.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {})


@pytest.fixture
def removedor_falso():
    return RemovedorFalso()
```

`tests/pipeline/test_batch.py`:
```python
import csv
import threading

from image_studio.core.export import ExportSettings
from image_studio.pipeline.batch import list_images, run_batch
from image_studio.pipeline.settings import PRESETS

AJUSTES = PRESETS["producto"]


def _leer_informe(carpeta):
    with open(carpeta / "informe.csv", encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def test_archivo_corrupto_no_detiene_el_lote(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada", tmp_path / "salida"
    for nombre in ("a.png", "b.png", "c.png"):
        escribir_png(entrada / nombre)
    (entrada / "roto.png").write_bytes(b"no es una imagen")
    items = run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert [item.estado for item in items] == ["ok", "ok", "ok", "error"]
    filas = _leer_informe(salida)
    assert len(filas) == 4
    assert filas[3]["archivo"] == "roto.png" and filas[3]["estado"] == "error"
    assert (salida / "a.png").exists()


def test_nombres_repetidos_no_se_pisan(tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    escribir_png(entrada / "a.png")
    escribir_png(entrada / "a.jpg")
    items = run_batch(entrada, tmp_path / "salida", removedor_falso, AJUSTES, ExportSettings())
    salidas = {item.salida.name for item in items}
    assert salidas == {"a.png", "a_png.png"}


def test_cancelar_detiene_el_lote(tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    for i in range(5):
        escribir_png(entrada / f"{i}.png")
    cancelar = threading.Event()
    items = run_batch(
        entrada, tmp_path / "salida", removedor_falso, AJUSTES, ExportSettings(),
        progreso=lambda hechos, total, item: cancelar.set(), cancelar=cancelar,
    )
    assert len(items) == 1


def test_cien_imagenes_sin_intervencion(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada", tmp_path / "salida"
    for i in range(100):
        escribir_png(entrada / f"img_{i:03d}.png")
    items = run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert len(items) == 100 and all(item.estado == "ok" for item in items)
    assert len(_leer_informe(salida)) == 100


def test_nombres_con_tildes(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada ñ", tmp_path / "salida ñ"
    escribir_png(entrada / "canción.png")
    run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert (salida / "canción.png").exists()
    assert _leer_informe(salida)[0]["archivo"] == "canción.png"


def test_lista_solo_imagenes(tmp_path, escribir_png):
    escribir_png(tmp_path / "a.png")
    (tmp_path / "informe.csv").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    assert [p.name for p in list_images(tmp_path)] == ["a.png"]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_batch.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.batch'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/batch.py`:
```python
"""Procesamiento por lotes con informe CSV."""

from __future__ import annotations

import csv
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from image_studio.core.export import ExportSettings, compose, save
from image_studio.core.image_io import FORMATOS_ENTRADA, load_image
from image_studio.pipeline.remove_bg import BackgroundRemover
from image_studio.pipeline.settings import PipelineSettings

NOMBRE_INFORME = "informe.csv"


@dataclass
class BatchItem:
    archivo: Path
    estado: str
    """Uno de: ok, baja_confianza, error."""
    tiempo_s: float
    motivo: str
    salida: Path | None


ProgresoLote = Callable[[int, int, BatchItem], None]


def list_images(carpeta: Path) -> list[Path]:
    return sorted(
        p for p in Path(carpeta).iterdir() if p.is_file() and p.suffix.lower() in FORMATOS_ENTRADA
    )


def run_batch(
    entrada: Path,
    salida: Path,
    removedor: BackgroundRemover,
    ajustes: PipelineSettings,
    exportar: ExportSettings,
    progreso: ProgresoLote | None = None,
    cancelar: threading.Event | None = None,
) -> list[BatchItem]:
    salida = Path(salida)
    archivos = list_images(entrada)
    usados: set[str] = set()
    items: list[BatchItem] = []
    for archivo in archivos:
        if cancelar is not None and cancelar.is_set():
            break
        inicio = perf_counter()
        destino = None
        try:
            doc = load_image(archivo)
            resultado = removedor.run(doc, ajustes)
            imagen = compose(resultado.rgb, resultado.alpha, exportar)
            destino = save(imagen, salida / _nombre_libre(archivo, exportar, usados), exportar, doc.icc_profile)
            estado = "baja_confianza" if resultado.baja_confianza else "ok"
            motivo = resultado.motivo_confianza
        except Exception as exc:  # un archivo con problemas no detiene el lote (V11)
            estado, motivo = "error", str(exc)
        items.append(BatchItem(archivo, estado, perf_counter() - inicio, motivo, destino))
        if progreso is not None:
            progreso(len(items), len(archivos), items[-1])
    write_report(items, salida / NOMBRE_INFORME)
    return items


def write_report(items: list[BatchItem], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["archivo", "estado", "tiempo_s", "motivo", "salida"])
        for item in items:
            escritor.writerow([
                item.archivo.name,
                item.estado,
                f"{item.tiempo_s:.3f}",
                item.motivo,
                item.salida.name if item.salida else "",
            ])


def _nombre_libre(archivo: Path, exportar: ExportSettings, usados: set[str]) -> str:
    nombre = f"{archivo.stem}.{exportar.formato}"
    if nombre.lower() in usados:
        nombre = f"{archivo.stem}_{archivo.suffix.lstrip('.').lower()}.{exportar.formato}"
    usados.add(nombre.lower())
    return nombre
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/batch.py tests/pipeline/test_batch.py tests/conftest.py
git commit -m "feat(pipeline): procesar carpetas por lotes con informe csv"
```

### Tarea 17: comando `batch` de la CLI

**Archivos:** crear `src/image_studio/cli.py`, `src/image_studio/__main__.py`, `tests/test_cli.py`;
modificar `README.md`

**Paso 1 - Tests que fallan** (`tests/test_cli.py`):
```python
import argparse

import pytest

from image_studio.cli import color_hex, main


def _fabrica(removedor):
    return lambda modelo, dispositivo, progreso: removedor


def test_lote_con_fondo_blanco_en_jpg(tmp_path, escribir_png, removedor_falso):
    escribir_png(tmp_path / "entrada" / "a.png")
    codigo = main(
        ["batch", str(tmp_path / "entrada"), str(tmp_path / "salida"), "--fondo", "blanco", "--formato", "jpg"],
        crear_removedor=_fabrica(removedor_falso),
    )
    assert codigo == 0
    assert (tmp_path / "salida" / "a.jpg").exists()
    assert (tmp_path / "salida" / "informe.csv").exists()


def test_carpeta_inexistente_devuelve_2(tmp_path, removedor_falso, capsys):
    codigo = main(["batch", str(tmp_path / "no"), str(tmp_path / "salida")], crear_removedor=_fabrica(removedor_falso))
    assert codigo == 2
    assert "no existe" in capsys.readouterr().err


def test_errores_devuelven_1(tmp_path, removedor_falso):
    (tmp_path / "entrada").mkdir()
    (tmp_path / "entrada" / "roto.png").write_bytes(b"x")
    codigo = main(["batch", str(tmp_path / "entrada"), str(tmp_path / "salida")], crear_removedor=_fabrica(removedor_falso))
    assert codigo == 1


def test_color_hex():
    assert color_hex("#00FF80") == (0, 255, 128)
    with pytest.raises(argparse.ArgumentTypeError):
        color_hex("verde")
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_cli.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.cli'`.

**Paso 3 - Implementar.**

`src/image_studio/cli.py`:
```python
"""Línea de comandos: python -m image_studio batch ENTRADA SALIDA [opciones]."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

from image_studio.core.export import FORMATOS_SALIDA, ExportSettings, Fondo
from image_studio.pipeline.batch import BatchItem, run_batch
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.settings import MODELOS_SEGMENTACION, PRESETS


def color_hex(valor: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
        raise argparse.ArgumentTypeError(f"Color inválido: {valor} (usar #RRGGBB)")
    return tuple(int(valor[i : i + 2], 16) for i in (1, 3, 5))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image_studio", description="Image Studio")
    comandos = parser.add_subparsers(dest="comando", required=True)
    lote = comandos.add_parser("batch", help="Quitar el fondo de todas las imágenes de una carpeta")
    lote.add_argument("entrada", type=Path)
    lote.add_argument("salida", type=Path)
    lote.add_argument("--preset", choices=sorted(PRESETS), default="producto")
    lote.add_argument("--modelo", choices=MODELOS_SEGMENTACION, help="Sustituye el modelo del preset")
    lote.add_argument("--formato", choices=sorted(FORMATOS_SALIDA), default="png")
    lote.add_argument("--fondo", choices=[f.value for f in Fondo], default=Fondo.TRANSPARENTE.value)
    lote.add_argument("--color", type=color_hex, default=(255, 255, 255), help="#RRGGBB para --fondo color")
    lote.add_argument("--recortar", action="store_true", help="Recortar al contenido")
    lote.add_argument("--margen", type=int, default=0, help="Margen en px al recortar")
    lote.add_argument("--dpi", type=int)
    lote.add_argument("--cpu", action="store_true", help="Forzar CPU")
    return parser


def main(argv: list[str] | None = None, crear_removedor=build_remover) -> int:
    args = build_parser().parse_args(argv)
    if not args.entrada.is_dir():
        print(f"La carpeta de entrada no existe: {args.entrada}", file=sys.stderr)
        return 2
    ajustes = PRESETS[args.preset]
    if args.modelo:
        ajustes = replace(ajustes, modelo=args.modelo)
    exportar = ExportSettings(
        formato=args.formato,
        fondo=Fondo(args.fondo),
        color=args.color,
        recortar=args.recortar,
        margen_px=args.margen,
        dpi=args.dpi,
    )
    removedor = crear_removedor(ajustes.modelo, "cpu" if args.cpu else "auto", _progreso_descarga)
    items = run_batch(args.entrada, args.salida, removedor, ajustes, exportar, progreso=_progreso_lote)
    conteo = Counter(item.estado for item in items)
    print(
        f"Listo: {conteo['ok']} ok, {conteo['baja_confianza']} baja confianza, "
        f"{conteo['error']} con error. Informe: {args.salida / 'informe.csv'}"
    )
    return 1 if conteo["error"] else 0


def _progreso_descarga(leidos: int, total: int) -> None:
    print(f"\rDescargando modelo: {leidos * 100 // max(total, 1)}%", end="", flush=True)
    if leidos >= total:
        print()


def _progreso_lote(hechos: int, total: int, item: BatchItem) -> None:
    detalle = f" ({item.motivo})" if item.motivo else ""
    print(f"[{hechos}/{total}] {item.archivo.name}: {item.estado}{detalle}")
```

`src/image_studio/__main__.py`:
```python
from image_studio.cli import main

raise SystemExit(main())
```

Agregar al final de `README.md`:
````markdown

## Uso (Hito 1: línea de comandos)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch fotos salida --preset producto
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch fotos salida --preset persona --fondo blanco --formato jpg --recortar --margen 40
```

La primera ejecución descarga el modelo a `%LOCALAPPDATA%\ImageStudio\models`. Cada lote deja
`informe.csv` en la carpeta de salida.
````

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_cli.py -q
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch --help
```
Esperado: `4 passed` y la ayuda con `--preset {persona,producto}`.

**Commit:**
```powershell
git add src/image_studio/cli.py src/image_studio/__main__.py tests/test_cli.py README.md
git commit -m "feat(cli): agregar comando batch para quitar fondos por carpeta"
```

---

## Fase E - Calidad y rendimiento

### Tarea 18: runner del golden set (V1, V2, V3)

**Archivos:** crear `tests/golden/test_golden.py`

Estructura esperada de la carpeta privada (fuera del repo):
```
%IMAGE_STUDIO_GOLDEN_DIR%\
  producto\<nombre>.jpg|png|...   + <nombre>.mask.png   (mínimo 8)
  persona\<nombre>.jpg|png|...    + <nombre>.mask.png   (mínimo 6)
  baseline.json                   (lo genera el test)
```

**Paso 1 - Test:**
```python
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
```

**Paso 2 - Verificar el comportamiento sin golden set:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/golden -q
```
Esperado: `3 skipped` (IMAGE_STUDIO_GOLDEN_DIR no definido).

**Paso 3 - Verificar con golden set** (cuando el usuario tenga las imágenes y máscaras):
```powershell
$env:IMAGE_STUDIO_GOLDEN_DIR = "D:\Johan\golden-image-studio"
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/golden -q
```
Esperado en la primera corrida: `2 passed, 1 skipped` (se crea `baseline.json`). Si V1 o V2
fallan, el resultado se documenta en el PR: es la evidencia para decidir ViTMatte (R1) o ajustar
presets en el Hito 3.

**Commit:**
```powershell
git add tests/golden/test_golden.py
git commit -m "test(golden): medir calidad y regresiones sobre el golden set privado"
```

### Tarea 19: benchmark de rendimiento (V4, V5)

**Archivos:** crear `scripts/benchmark.py`

Sin test unitario: es una medición en el equipo objetivo.

**Paso 1 - Implementar** `scripts/benchmark.py`:
```python
"""Mide el pipeline completo sobre una imagen de 4000x3000 (criterios V4 y V5 de la spec).

Uso: .\\.venv\\Scripts\\python.exe -X utf8 scripts\\benchmark.py RUTA_IMAGEN [--cpu] [--preset persona]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from time import perf_counter

import cv2

from image_studio.core.image_io import load_image
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.settings import PRESETS

TAMANO = (4000, 3000)
LIMITE_S = {"auto": 5.0, "cpu": 60.0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark del pipeline de quitar fondos")
    parser.add_argument("imagen", type=Path)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="persona")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()

    dispositivo = "cpu" if args.cpu else "auto"
    ajustes = PRESETS[args.preset]
    doc = load_image(args.imagen)
    if doc.size != TAMANO:
        doc.rgb = cv2.resize(doc.rgb, TAMANO, interpolation=cv2.INTER_CUBIC)
        doc.alpha = None
    removedor = build_remover(ajustes.modelo, dispositivo)
    removedor.run(doc, ajustes)  # calentamiento: sesión ONNX y compilación de numba

    tiempos = []
    for i in range(args.repeticiones):
        inicio = perf_counter()
        resultado = removedor.run(doc, ajustes)
        tiempos.append(perf_counter() - inicio)
        etapas = ", ".join(f"{k} {v:.2f}s" for k, v in resultado.tiempos.items())
        print(f"corrida {i + 1}: {tiempos[-1]:.2f}s ({etapas})")
    mediana = statistics.median(tiempos)
    limite = LIMITE_S[dispositivo]
    estado = "OK" if mediana <= limite else "FUERA DE LIMITE"
    print(f"mediana {mediana:.2f}s, limite {limite:.0f}s ({dispositivo}): {estado}")
    return 0 if mediana <= limite else 1


if __name__ == "__main__":
    sys.exit(main())
```

**Paso 2 - Ejecutar con una foto real de persona** (copiarla antes a `D:\Johan\pruebas\entrada\persona.jpg`, fuera del repo):
```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\benchmark.py D:\Johan\pruebas\entrada\persona.jpg
.\.venv\Scripts\python.exe -X utf8 scripts\benchmark.py D:\Johan\pruebas\entrada\persona.jpg --cpu --repeticiones 1
```
Esperado según las mediciones previas: GPU alrededor de 4.5 s (segmentación 1.5 s, matting
unos 2.5 s, limpieza menos de 1 s), dentro de 5 s; CPU dentro de 60 s. Anotar los números en
el PR. Si GPU supera 5 s, la etapa que más pese se documenta como deuda del Hito 2.

**Commit:**
```powershell
git add scripts/benchmark.py
git commit -m "perf(pipeline): agregar benchmark de tiempo por imagen"
```

### Tarea 20: cierre del hito

Sin archivos nuevos.

**Paso 1 - Suite completa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```
Esperado: todo `passed`; `skipped` solo en `tests/golden` si no hay golden set.

**Paso 2 - Prueba manual de punta a punta** con 3 a 5 fotos reales en una carpeta fuera del repo:
```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch D:\Johan\pruebas\entrada D:\Johan\pruebas\salida --preset persona
```
Esperado: un PNG por foto e `informe.csv`; abrir los PNG y revisar bordes a mano.

**Paso 3 - PR a develop:**
```powershell
git push -u origin feature/hito-1-motor
gh pr create --base develop --title "feat(pipeline): motor y cli de quitar fondos (hito 1)"
```
El cuerpo del PR incluye: qué cambia, por qué, archivos, resultado de la suite, números del
benchmark (GPU y CPU), resultado del golden set si existe, y modelos tocados (BiRefNet e ISNet,
con sus SHA-256). Integración por squash.

---

## Cobertura de la spec en este hito

| Requisito | Tarea |
|---|---|
| Formatos de entrada, EXIF, CMYK, 16 bits, HEIC, alfa existente | 4, 14 |
| BiRefNet calidad e ISNet rápido | 9, 10 |
| Trimap, matting, limpieza de color, desplazamiento y suavizado de borde | 5, 11, 12, 14 |
| Presets Producto y Persona | 13 |
| Baja confianza | 14 |
| Lote con informe CSV, cancelación, CLI | 16, 17 |
| Exportación PNG/WebP/JPG, fondo, recorte, margen, DPI | 6 |
| Modelos con descarga, hash y respaldo a CPU | 8 |
| V1, V2, V3 | 18 |
| V4, V5 | 19 |
| V7 | 6 |
| V9, V11 | 16 |
| V10 | 3 |
| V12 | 4, 6, 16 |
| V6, V8, lienzo, pinceles, historial | Hito 2 |
| Presets propios, UI de lotes y exportación, `Tool`, ViTMatte | Hito 3 |
