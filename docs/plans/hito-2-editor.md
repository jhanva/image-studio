# Plan de implementación - Hito 2: editor

Spec: [../spec.md](../spec.md). Flujo: [../repo-workflow.md](../repo-workflow.md).
Hito anterior: [hito-1-motor.md](hito-1-motor.md).
Rama: `feature/hito-2-editor` desde `develop`. Un commit por tarea; PR a `develop` (squash) al final.

## Objetivo del hito

Una ventana de escritorio para abrir una imagen (diálogo, arrastrar y soltar, pegar), quitar el
fondo en segundo plano con el motor del Hito 1, ver el resultado sobre tablero de transparencia
con zoom y comparación antes/después, retocar con los pinceles Conservar, Borrar y Refinar
borde, deshacer y rehacer, y guardar un PNG transparente.

Fuera de este hito (Hito 3): interfaz `Tool` de la suite, panel de lotes, presets propios,
diálogo completo de exportación (formato, fondo, recorte, DPI) y ViTMatte.

## Decisiones tomadas con mediciones (2026-10-23, Python 3.14.7, PySide6-Essentials 6.12.0)

| Pregunta | Medición | Decisión |
|---|---|---|
| ¿QImage puede leer un arreglo numpy sin copiar? | Cambiar el arreglo cambia `QImage.pixel()` | El lienzo actualiza solo el rectángulo pintado del buffer RGBA |
| ¿Hace falta pirámide de resoluciones para imágenes grandes? | `drawImage` 10000x8000 a 1600x1000: 8 ms con suavizado | Sin pirámide; la spec se actualiza |
| ¿Cumple V6 (refinar 500x500 en <= 2 s)? | Región de 500x500 con trazo de 40 px sobre el borde: 0.34 s | Refinar corre en un hilo de trabajo con el matting clásico paralelo |
| ¿Funcionan los tests de UI sin pantalla? | `QT_QPA_PLATFORM=offscreen`: ventana, eventos de ratón sintéticos y portapapeles funcionan | Tests con `pytest-qt` en modo offscreen |
| ¿`constBits()` sirve para pegar desde el portapapeles? | Devuelve `memoryview` con el tamaño de `sizeInBytes()` | `qimage_to_arrays` copia desde ese buffer |

## Mapa de archivos

- Modificar: `docs/spec.md`, `requirements.txt`, `requirements-dev.txt`, `tests/conftest.py`,
  `src/image_studio/__main__.py`, `scripts/benchmark.py`, `README.md`
- Crear (sin Qt): `src/image_studio/core/history.py`, `src/image_studio/core/brush.py`,
  `src/image_studio/pipeline/refine_region.py`, `src/image_studio/pipeline/session.py`
- Crear (Qt): `src/image_studio/ui/__init__.py`, `ui/qt_image.py`, `ui/canvas/__init__.py`,
  `ui/canvas/layer.py`, `ui/canvas/view.py`, `ui/main_window.py`, `ui/app.py`,
  `src/image_studio/workers/__init__.py`, `workers/tasks.py`
- Crear tests: `tests/core/test_history.py`, `tests/core/test_brush.py`,
  `tests/pipeline/test_refine_region.py`, `tests/pipeline/test_session.py`,
  `tests/ui/test_entorno_qt.py`, `tests/ui/test_qt_image.py`, `tests/ui/test_layer.py`,
  `tests/ui/test_view.py`, `tests/ui/test_main_window.py`, `tests/ui/test_app.py`,
  `tests/workers/test_tasks.py`, `tests/test_main.py`

Las rutas `ui/...` y `workers/...` son relativas a `src/image_studio/`. Comandos desde la raíz
del repo en PowerShell. `__init__.py` nuevos se crean vacíos.

---

## Fase A - Base

### Tarea 1: actualizar la spec

**Archivos:** modificar `docs/spec.md`

Sin test (documental). Cambios exactos:

1. Tabla 3.1: reemplazar `| UI | PySide6 + tema oscuro (PyQtDarkTheme o QSS propio) |` por
   `| UI | PySide6-Essentials + estilo Fusion con paleta oscura propia |`.
2. Tabla 3.6: reemplazar la fila que empieza con `| Imagen mayor a 8000 px por lado |` por
   `| Imagen mayor a 8000 px por lado | Matting por tiles; el lienzo dibuja solo la zona visible (medido: 8 ms por cuadro a 10000x8000), sin pirámide |`.
3. Árbol 3.4: reemplazar la línea `      mask_ops.py         # suavizado, desplazamiento, umbral, recorte al contenido`
   por esa misma línea seguida de `      brush.py            # huella y estampado de pinceles`;
   agregar bajo `pipeline/`, después de `factory.py`, las líneas
   `      session.py          # sesión de edición: máscara, historial, pinceles, exportar` y
   `      refine_region.py    # matting solo sobre la zona pintada con Refinar borde`;
   reemplazar las líneas de `ui/` (desde `    ui/                   # PySide6` hasta
   `      export_dialog.py`) por:
   ```
       ui/                   # PySide6
         app.py              # arranque y tema
         main_window.py      # acciones, barra de herramientas y estado
         qt_image.py         # buffers numpy que respaldan QImage sin copia
         canvas/             # QGraphicsView: capa de imagen, tablero, zoom, trazos
         batch_panel.py      # Hito 3
         export_dialog.py    # Hito 3
   ```
   y reemplazar `    workers/              # QThreadPool: inferencia con progreso y cancelación`
   por `    workers/              # QThreadPool: tareas en segundo plano con señales`.
4. Sección 3.7, línea de entregas por hitos: reemplazar `Hito 2 editor;` por
   `Hito 2 editor (incluye guardar PNG transparente);`.

**Verificar:**
```powershell
Select-String -Path docs\spec.md -Pattern "PySide6-Essentials","sin pirámide","brush.py","session.py","refine_region.py","qt_image.py","guardar PNG transparente"
```
Esperado: 7 coincidencias.

**Commit:**
```powershell
git add docs/spec.md
git commit -m "docs(spec): ajustar diseño del editor a las mediciones del hito 2"
```

### Tarea 2: dependencias de Qt y entorno de tests sin pantalla

**Archivos:** modificar `requirements.txt`, `requirements-dev.txt`, `tests/conftest.py`;
crear `tests/ui/test_entorno_qt.py`

**Paso 1 - Test que falla** (`tests/ui/test_entorno_qt.py`):
```python
def test_qt_corre_sin_pantalla(qapp):
    assert qapp.platformName() == "offscreen"
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_entorno_qt.py -q
```
Esperado: `fixture 'qapp' not found` (sin pytest-qt) o `AssertionError` con plataforma
`windows` (si pytest-qt ya está instalado).

**Paso 3 - Implementar.**

Agregar al final de `requirements.txt`:
```text
PySide6-Essentials==6.12.0
```

Agregar al final de `requirements-dev.txt`:
```text
pytest-qt==4.5.0
```

En `tests/conftest.py`, insertar al inicio del archivo (antes de `from pathlib import Path`):
```python
import os

# Los tests de interfaz corren sin ventana visible; debe fijarse antes de crear la QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

```powershell
.\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt
```

**Paso 4 - Verificar que pasa:** mismo comando del paso 2. Esperado: `1 passed`.

**Commit:**
```powershell
git add requirements.txt requirements-dev.txt tests/conftest.py tests/ui/test_entorno_qt.py
git commit -m "build(ui): agregar pyside6 y tests de interfaz sin pantalla"
```

---

## Fase B - Núcleo de edición sin Qt

### Tarea 3: historial por tiles (V8)

**Archivos:** crear `src/image_studio/core/history.py`, `tests/core/test_history.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest

from image_studio.core.history import MaskHistory

BYTES_TILE = 256 * 256 * 4


def _paso(historial, mascara, rect, valor):
    historial.begin()
    historial.touch(*rect)
    x0, y0, x1, y1 = rect
    mascara[y0:y1, x0:x1] = valor
    historial.end()


def test_deshacer_y_rehacer():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (10, 10, 20, 20), 1.0)
    assert historial.undo() == [(0, 0, 256, 256)]
    assert (mascara == 0).all()
    historial.redo()
    assert mascara[15, 15] == 1.0


def test_paso_nuevo_borra_rehacer():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (0, 0, 10, 10), 1.0)
    historial.undo()
    _paso(historial, mascara, (0, 0, 10, 10), 0.5)
    assert not historial.puede_rehacer


def test_tocar_dos_veces_conserva_el_estado_original():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    historial.begin()
    historial.touch(0, 0, 10, 10)
    mascara[0:10, 0:10] = 0.5
    historial.touch(0, 0, 10, 10)
    mascara[0:10, 0:10] = 1.0
    historial.end()
    historial.undo()
    assert (mascara == 0).all()


def test_paso_vacio_no_se_guarda():
    historial = MaskHistory(np.zeros((10, 10), np.float32))
    historial.begin()
    historial.end()
    assert not historial.puede_deshacer


def test_limite_de_pasos():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara, max_pasos=2)
    for valor in (1.0, 2.0, 3.0):
        _paso(historial, mascara, (0, 0, 1, 1), valor)
    historial.undo()
    historial.undo()
    assert mascara[0, 0] == 1.0
    assert not historial.puede_deshacer


def test_limite_de_memoria():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara, max_bytes=2 * BYTES_TILE)
    for valor in (1.0, 2.0, 3.0):
        _paso(historial, mascara, (0, 0, 1, 1), valor)
    assert historial.bytes_usados == 2 * BYTES_TILE


def test_tiles_del_borde():
    mascara = np.zeros((300, 300), np.float32)
    historial = MaskHistory(mascara)
    _paso(historial, mascara, (250, 250, 300, 300), 1.0)
    assert sorted(historial.undo()) == [
        (0, 0, 256, 256),
        (0, 256, 256, 300),
        (256, 0, 300, 256),
        (256, 256, 300, 300),
    ]


def test_errores_de_uso():
    historial = MaskHistory(np.zeros((10, 10), np.float32))
    with pytest.raises(RuntimeError):
        historial.touch(0, 0, 1, 1)
    with pytest.raises(RuntimeError):
        historial.end()
    historial.begin()
    with pytest.raises(RuntimeError):
        historial.begin()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_history.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.history'`.

**Paso 3 - Implementar** `src/image_studio/core/history.py`:
```python
"""Historial deshacer/rehacer de la máscara guardando solo los tiles que cambia cada paso."""

from __future__ import annotations

from collections import deque

import numpy as np

Rect = tuple[int, int, int, int]
_Paso = dict[tuple[int, int], np.ndarray]


class MaskHistory:
    """La máscara se modifica en el lugar; antes de cambiar una zona se llama a touch()."""

    def __init__(
        self, mascara: np.ndarray, tile: int = 256, max_pasos: int = 50, max_bytes: int = 1 << 30
    ):
        self.mascara = mascara
        self.tile = tile
        self.max_pasos = max_pasos
        self.max_bytes = max_bytes
        self._deshacer: deque[_Paso] = deque()
        self._rehacer: list[_Paso] = []
        self._actual: _Paso | None = None

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._deshacer)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self._rehacer)

    @property
    def bytes_usados(self) -> int:
        pasos = list(self._deshacer) + self._rehacer
        return sum(tile.nbytes for paso in pasos for tile in paso.values())

    def begin(self) -> None:
        if self._actual is not None:
            raise RuntimeError("Ya hay un paso abierto")
        self._actual = {}

    def touch(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Guarda el estado previo de los tiles que cubren el rectángulo, una vez por paso."""
        if self._actual is None:
            raise RuntimeError("touch() sin begin()")
        alto, ancho = self.mascara.shape
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(ancho, x1), min(alto, y1)
        if x0 >= x1 or y0 >= y1:
            return
        t = self.tile
        for ty in range(y0 // t, (y1 - 1) // t + 1):
            for tx in range(x0 // t, (x1 - 1) // t + 1):
                if (ty, tx) not in self._actual:
                    self._actual[(ty, tx)] = self.mascara[ty * t : (ty + 1) * t, tx * t : (tx + 1) * t].copy()

    def end(self) -> None:
        if self._actual is None:
            raise RuntimeError("end() sin begin()")
        paso, self._actual = self._actual, None
        if not paso:
            return
        self._deshacer.append(paso)
        self._rehacer.clear()
        while len(self._deshacer) > self.max_pasos or (
            len(self._deshacer) > 1 and self.bytes_usados > self.max_bytes
        ):
            self._deshacer.popleft()

    def undo(self) -> list[Rect]:
        if not self._deshacer:
            return []
        paso = self._deshacer.pop()
        self._rehacer.append(paso)
        return self._intercambiar(paso)

    def redo(self) -> list[Rect]:
        if not self._rehacer:
            return []
        paso = self._rehacer.pop()
        self._deshacer.append(paso)
        return self._intercambiar(paso)

    def _intercambiar(self, paso: _Paso) -> list[Rect]:
        """Pone en la máscara lo guardado y guarda lo que había: el paso queda listo para el sentido contrario."""
        t = self.tile
        rects = []
        for (ty, tx), guardado in paso.items():
            zona = self.mascara[ty * t : (ty + 1) * t, tx * t : (tx + 1) * t]
            actual = zona.copy()
            zona[...] = guardado
            paso[(ty, tx)] = actual
            alto, ancho = zona.shape
            rects.append((tx * t, ty * t, tx * t + ancho, ty * t + alto))
        return rects
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `8 passed`.

**Commit:**
```powershell
git add src/image_studio/core/history.py tests/core/test_history.py
git commit -m "feat(core): agregar historial de mascara por tiles"
```

### Tarea 4: pinceles

**Archivos:** crear `src/image_studio/core/brush.py`, `tests/core/test_brush.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest

from image_studio.core.brush import (
    Modo,
    brush_profile,
    footprint_rect,
    stamp,
    stroke_points,
    union,
)


def test_huella_suave():
    huella = brush_profile(10, 0.5)
    assert huella.shape == (21, 21) and huella.dtype == np.float32
    assert huella[10, 10] == 1.0
    assert huella[0, 0] == 0.0
    assert huella[10, 2] == pytest.approx(0.4)


def test_huella_dura_es_binaria():
    assert set(np.unique(brush_profile(5, 1.0))) <= {0.0, 1.0}


def test_parametros_invalidos():
    with pytest.raises(ValueError):
        brush_profile(0, 0.5)
    with pytest.raises(ValueError):
        brush_profile(5, 1.5)


def test_rectangulo_de_la_huella():
    huella = brush_profile(5, 1.0)
    assert footprint_rect(25, 25, huella, (50, 50)) == (20, 20, 31, 31)
    assert footprint_rect(0, 0, huella, (50, 50)) == (0, 0, 6, 6)
    assert footprint_rect(-50, -50, huella, (50, 50)) is None


def test_conservar_sube_el_alfa():
    mascara = np.full((50, 50), 0.3, np.float32)
    assert stamp(mascara, 25, 25, brush_profile(5, 1.0), Modo.CONSERVAR) == (20, 20, 31, 31)
    assert mascara[25, 25] == 1.0 and mascara[0, 0] == pytest.approx(0.3)


def test_borrar_baja_el_alfa():
    mascara = np.ones((50, 50), np.float32)
    stamp(mascara, 25, 25, brush_profile(5, 1.0), Modo.BORRAR)
    assert mascara[25, 25] == 0.0 and mascara[0, 0] == 1.0


def test_refinar_no_se_estampa():
    with pytest.raises(ValueError):
        stamp(np.ones((10, 10), np.float32), 5, 5, brush_profile(2, 1.0), Modo.REFINAR)


def test_puntos_del_trazo():
    puntos = stroke_points((0, 0), (10, 0), paso=2.5)
    assert len(puntos) == 4 and puntos[-1] == (10.0, 0.0)


def test_union_de_rectangulos():
    assert union(None, (1, 1, 2, 2)) == (1, 1, 2, 2)
    assert union((0, 0, 5, 5), (3, 3, 8, 9)) == (0, 0, 8, 9)
    assert union(None, None) is None
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/core/test_brush.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.core.brush'`.

**Paso 3 - Implementar** `src/image_studio/core/brush.py`:
```python
"""Pinceles sobre la máscara: Conservar sube el alfa, Borrar lo baja, Refinar marca zonas."""

from __future__ import annotations

from enum import Enum

import numpy as np

Rect = tuple[int, int, int, int]


class Modo(str, Enum):
    CONSERVAR = "conservar"
    BORRAR = "borrar"
    REFINAR = "refinar"


def brush_profile(radio: float, dureza: float) -> np.ndarray:
    """Huella cuadrada float32: 1 hasta radio*dureza y caída lineal hasta 0 en el radio."""
    if radio < 0.5:
        raise ValueError("radio debe ser >= 0.5")
    if not 0.0 <= dureza <= 1.0:
        raise ValueError("dureza debe estar entre 0 y 1")
    r = int(np.ceil(radio))
    filas, columnas = np.mgrid[-r : r + 1, -r : r + 1]
    distancia = np.hypot(filas, columnas)
    nucleo = radio * dureza
    if radio - nucleo < 1e-6:
        return (distancia <= radio).astype(np.float32)
    return np.clip((radio - distancia) / (radio - nucleo), 0.0, 1.0).astype(np.float32)


def footprint_rect(cx: float, cy: float, huella: np.ndarray, forma: tuple[int, int]) -> Rect | None:
    """Rectángulo (x0, y0, x1, y1) que cubre la huella centrada en (cx, cy), recortado a la imagen."""
    r = huella.shape[0] // 2
    alto, ancho = forma
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    x1, y1 = x0 + huella.shape[1], y0 + huella.shape[0]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(ancho, x1), min(alto, y1)
    if x0 >= x1 or y0 >= y1:
        return None
    return x0, y0, x1, y1


def huella_en(cx: float, cy: float, huella: np.ndarray, rect: Rect) -> np.ndarray:
    """Parte de la huella que cae dentro de rect (obtenido con footprint_rect)."""
    r = huella.shape[0] // 2
    ox, oy = int(round(cx)) - r, int(round(cy)) - r
    x0, y0, x1, y1 = rect
    return huella[y0 - oy : y1 - oy, x0 - ox : x1 - ox]


def stamp(mascara: np.ndarray, cx: float, cy: float, huella: np.ndarray, modo: Modo) -> Rect | None:
    rect = footprint_rect(cx, cy, huella, mascara.shape)
    if rect is None:
        return None
    x0, y0, x1, y1 = rect
    zona = mascara[y0:y1, x0:x1]
    parte = huella_en(cx, cy, huella, rect)
    if modo is Modo.CONSERVAR:
        np.maximum(zona, parte, out=zona)
    elif modo is Modo.BORRAR:
        np.minimum(zona, 1.0 - parte, out=zona)
    else:
        raise ValueError("stamp solo pinta con Conservar o Borrar")
    return rect


def stroke_points(
    desde: tuple[float, float], hasta: tuple[float, float], paso: float
) -> list[tuple[float, float]]:
    """Puntos entre dos posiciones separados como máximo por paso px; no incluye desde."""
    (xa, ya), (xb, yb) = desde, hasta
    n = max(1, int(np.ceil(float(np.hypot(xb - xa, yb - ya)) / max(paso, 1e-6))))
    return [(xa + (xb - xa) * i / n, ya + (yb - ya) * i / n) for i in range(1, n + 1)]


def union(a: Rect | None, b: Rect | None) -> Rect | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `9 passed`.

**Commit:**
```powershell
git add src/image_studio/core/brush.py tests/core/test_brush.py
git commit -m "feat(core): agregar pinceles conservar, borrar y refinar"
```

### Tarea 5: refinar borde en una región

**Archivos:** crear `src/image_studio/pipeline/refine_region.py`,
`tests/pipeline/test_refine_region.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np

from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.refine_region import refine_region, region_bbox


class MatterFijo:
    nombre = "fijo"

    def __init__(self):
        self.trimap = None

    def refine(self, rgb, trimap, grueso):
        self.trimap = trimap
        return np.full(grueso.shape, 0.42, np.float32)


def _medio_y_medio(n: int = 100):
    alfa = np.zeros((n, n), np.float32)
    alfa[:, n // 2 :] = 1.0
    pintado = np.zeros((n, n), bool)
    pintado[40:60, 45:55] = True
    return alfa, pintado


def test_caja_de_la_region():
    _, pintado = _medio_y_medio()
    assert region_bbox(pintado, margen=8) == (37, 32, 63, 68)
    assert region_bbox(np.zeros((10, 10), bool)) is None


def test_solo_cambia_lo_pintado():
    alfa, pintado = _medio_y_medio()
    caja = region_bbox(pintado, margen=8)
    rect = refine_region(np.zeros((100, 100, 3), np.uint8), alfa, pintado, MatterFijo(), caja)
    assert rect == caja
    assert np.allclose(alfa[pintado], 0.42)
    assert alfa[0, 0] == 0.0 and alfa[0, 99] == 1.0


def test_trimap_desconocido_solo_en_lo_pintado():
    alfa, pintado = _medio_y_medio()
    matter = MatterFijo()
    caja = region_bbox(pintado, margen=8)
    refine_region(np.zeros((100, 100, 3), np.uint8), alfa, pintado, matter, caja)
    x0, y0, x1, y1 = caja
    assert ((matter.trimap == DESCONOCIDO) == pintado[y0:y1, x0:x1]).all()
    assert matter.trimap[0, 0] == FONDO and matter.trimap[0, -1] == FRENTE


def test_matting_real_mejora_el_borde():
    n = 200
    filas, columnas = np.mgrid[:n, :n]
    real = np.clip((columnas - 100 + 20 * np.sin(filas / 15)) / 5 + 0.5, 0, 1).astype(np.float32)
    rng = np.random.default_rng(0)
    rgb = (real[..., None] * np.array([90, 60, 40]) + (1 - real[..., None]) * rng.uniform(150, 230, (n, n, 3))).astype(np.uint8)
    alfa = (real >= 0.5).astype(np.float32)
    grueso = alfa.copy()
    pintado = (real > 0.02) & (real < 0.98)
    refine_region(rgb, alfa, pintado, ClassicMatter(tile=64, margen=16), region_bbox(pintado))
    assert np.abs(alfa - real)[pintado].mean() < np.abs(grueso - real)[pintado].mean()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_refine_region.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.refine_region'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/refine_region.py`:
```python
"""Refinar borde: matting solo sobre los píxeles pintados con el pincel Refinar."""

from __future__ import annotations

import numpy as np

from image_studio.core.brush import Rect
from image_studio.core.mask_ops import DESCONOCIDO, FONDO, FRENTE
from image_studio.engines.base import Matter


def region_bbox(pintado: np.ndarray, margen: int = 32) -> Rect | None:
    """Caja de lo pintado con margen, recortada a la imagen; el margen da frente y fondo conocidos."""
    filas, columnas = np.nonzero(pintado)
    if filas.size == 0:
        return None
    alto, ancho = pintado.shape
    return (
        max(0, int(columnas.min()) - margen),
        max(0, int(filas.min()) - margen),
        min(ancho, int(columnas.max()) + 1 + margen),
        min(alto, int(filas.max()) + 1 + margen),
    )


def refine_region(
    rgb: np.ndarray, alpha: np.ndarray, pintado: np.ndarray, matter: Matter, caja: Rect
) -> Rect:
    """Modifica alpha en el lugar, solo en los píxeles pintados de la caja."""
    x0, y0, x1, y1 = caja
    alfa = alpha[y0:y1, x0:x1]
    region = pintado[y0:y1, x0:x1]
    trimap = np.where(alfa >= 0.5, FRENTE, FONDO).astype(np.uint8)
    trimap[region] = DESCONOCIDO
    refinado = matter.refine(rgb[y0:y1, x0:x1], trimap, alfa)
    alfa[region] = refinado[region]
    return caja
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/refine_region.py tests/pipeline/test_refine_region.py
git commit -m "feat(pipeline): refinar borde solo en la region pintada"
```

### Tarea 6: sesión de edición (V8)

**Archivos:** crear `src/image_studio/pipeline/session.py`, `tests/pipeline/test_session.py`

**Paso 1 - Tests que fallan:**
```python
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from image_studio.core.brush import Modo
from image_studio.core.export import ExportSettings
from image_studio.core.image_io import ImageDoc
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.session import EditSession, Pincel


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


def _doc(n: int = 200) -> ImageDoc:
    return ImageDoc(Path("x.png"), np.full((n, n, 3), 128, np.uint8), None, None, None)


def _resultado(doc: ImageDoc) -> RemovalResult:
    alfa = np.zeros(doc.rgb.shape[:2], np.float32)
    alfa[50:150, 50:150] = 1.0
    return RemovalResult(doc.rgb.copy(), alfa, None, False, "", {})


def test_sin_alfa_empieza_opaca():
    sesion = EditSession(_doc())
    assert (sesion.alpha == 1.0).all()
    assert not sesion.history.puede_deshacer


def test_aplicar_resultado_se_puede_deshacer():
    doc = _doc()
    resultado = _resultado(doc)
    sesion = EditSession(doc)
    assert sesion.apply_result(resultado) == (0, 0, 200, 200)
    assert np.array_equal(sesion.alpha, resultado.alpha) and sesion.rgb is resultado.rgb
    sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_trazo_borrar_y_deshacer():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.BORRAR, radio=10, dureza=1.0)
    assert sesion.begin_stroke(50, 100) == (40, 90, 61, 111)
    sesion.move_stroke(150, 100)
    sesion.end_stroke()
    assert sesion.alpha[100, 100] == 0.0 and sesion.alpha[0, 0] == 1.0
    assert sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_trazo_conservar():
    doc = _doc()
    sesion = EditSession(doc)
    sesion.apply_result(_resultado(doc))
    sesion.pincel = Pincel(Modo.CONSERVAR, radio=5, dureza=1.0)
    sesion.begin_stroke(10, 10)
    sesion.end_stroke()
    assert sesion.alpha[10, 10] == 1.0


def test_refinar_queda_pendiente_hasta_el_matting():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.REFINAR, radio=5, dureza=1.0)
    sesion.begin_stroke(100, 100)
    sesion.move_stroke(120, 100)
    sesion.end_stroke()
    assert sesion.refinado_pendiente and (sesion.alpha == 1.0).all()
    assert sesion.refine_pending(MatterFijo()) is not None
    assert not sesion.refinado_pendiente
    assert sesion.alpha[100, 110] == pytest.approx(0.42)
    sesion.undo()
    assert (sesion.alpha == 1.0).all()


def test_cancelar_refinado():
    sesion = EditSession(_doc())
    sesion.pincel = Pincel(Modo.REFINAR, radio=5, dureza=1.0)
    sesion.begin_stroke(100, 100)
    sesion.end_stroke()
    sesion.cancel_refine()
    assert not sesion.refinado_pendiente and not sesion.trazo_abierto
    sesion.undo()


def test_no_deshace_con_trazo_abierto():
    sesion = EditSession(_doc())
    sesion.begin_stroke(10, 10)
    with pytest.raises(RuntimeError):
        sesion.undo()


def test_mover_sin_trazo_no_hace_nada():
    assert EditSession(_doc()).move_stroke(1, 1) is None


def test_exporta_png(tmp_path):
    doc = _doc()
    sesion = EditSession(doc)
    sesion.apply_result(_resultado(doc))
    ruta = sesion.export(tmp_path / "a.png", ExportSettings(), limpiar_color=False)
    with Image.open(ruta) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[100, 100] == 255


def test_v8_cincuenta_trazos_en_6000x4000():
    doc = ImageDoc(Path("g.png"), np.zeros((4000, 6000, 3), np.uint8), None, None, None)
    sesion = EditSession(doc)
    sesion.pincel = Pincel(Modo.BORRAR, radio=30, dureza=0.8)
    rng = np.random.default_rng(0)
    for _ in range(50):
        x, y = rng.uniform(100, 5600), rng.uniform(100, 3800)
        sesion.begin_stroke(x, y)
        sesion.move_stroke(x + 300, y + 50)
        sesion.end_stroke()
    assert (sesion.alpha < 1.0).any()
    assert sesion.history.bytes_usados < 1 << 30
    for _ in range(50):
        sesion.undo()
    assert (sesion.alpha == 1.0).all()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_session.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.session'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/session.py`:
```python
"""Sesión de edición: máscara, historial, pinceles y exportación, sin dependencias de Qt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from image_studio.core.brush import (
    Modo,
    Rect,
    brush_profile,
    footprint_rect,
    huella_en,
    stamp,
    stroke_points,
    union,
)
from image_studio.core.export import ExportSettings, compose, save
from image_studio.core.history import MaskHistory
from image_studio.core.image_io import ImageDoc
from image_studio.engines.base import Matter
from image_studio.engines.decontaminate import decontaminate
from image_studio.pipeline.refine_region import refine_region, region_bbox
from image_studio.pipeline.remove_bg import RemovalResult


@dataclass
class Pincel:
    modo: Modo = Modo.CONSERVAR
    radio: float = 30.0
    dureza: float = 0.8


class EditSession:
    def __init__(self, doc: ImageDoc):
        self.doc = doc
        alto, ancho = doc.rgb.shape[:2]
        if doc.alpha is not None:
            self.alpha = doc.alpha.astype(np.float32, copy=True)
        else:
            self.alpha = np.ones((alto, ancho), np.float32)
        self.rgb = doc.rgb
        """Color que se muestra: el original o el limpiado por el último quitar fondo."""
        self.resultado: RemovalResult | None = None
        self.history = MaskHistory(self.alpha)
        self.pincel = Pincel()
        self.refinado_pendiente = False
        self._modo: Modo | None = None
        self._ultimo: tuple[float, float] | None = None
        self._huella: np.ndarray | None = None
        self._pintado: np.ndarray | None = None

    @property
    def rect_completo(self) -> Rect:
        alto, ancho = self.alpha.shape
        return 0, 0, ancho, alto

    @property
    def trazo_abierto(self) -> bool:
        return self._ultimo is not None or self.refinado_pendiente

    def apply_result(self, resultado: RemovalResult) -> Rect:
        self._exigir_sin_trazo()
        self.history.begin()
        self.history.touch(*self.rect_completo)
        self.alpha[...] = resultado.alpha
        self.history.end()
        self.rgb = resultado.rgb
        self.resultado = resultado
        return self.rect_completo

    def begin_stroke(self, x: float, y: float) -> Rect | None:
        self._exigir_sin_trazo()
        self.history.begin()
        self._modo = self.pincel.modo
        self._huella = brush_profile(self.pincel.radio, self.pincel.dureza)
        if self._modo is Modo.REFINAR:
            self._pintado = np.zeros(self.alpha.shape, bool)
        self._ultimo = (x, y)
        return self._aplicar(x, y)

    def move_stroke(self, x: float, y: float) -> Rect | None:
        if self._ultimo is None:
            return None
        rect = None
        for px, py in stroke_points(self._ultimo, (x, y), paso=max(1.0, self.pincel.radio / 4)):
            rect = union(rect, self._aplicar(px, py))
        self._ultimo = (x, y)
        return rect

    def end_stroke(self) -> None:
        if self._ultimo is None:
            return
        self._ultimo = None
        self._huella = None
        if self._modo is Modo.REFINAR:
            # El paso del historial sigue abierto hasta que el matting termina en otro hilo.
            self.refinado_pendiente = True
        else:
            self.history.end()

    def refine_pending(self, matter: Matter) -> Rect | None:
        if not self.refinado_pendiente:
            return None
        pintado, self._pintado = self._pintado, None
        caja = region_bbox(pintado)
        rect = None
        if caja is not None:
            self.history.touch(*caja)
            rect = refine_region(self.doc.rgb, self.alpha, pintado, matter, caja)
        self.history.end()
        self.refinado_pendiente = False
        return rect

    def cancel_refine(self) -> None:
        if not self.refinado_pendiente:
            return
        self._pintado = None
        self.history.end()
        self.refinado_pendiente = False

    def undo(self) -> list[Rect]:
        self._exigir_sin_trazo()
        return self.history.undo()

    def redo(self) -> list[Rect]:
        self._exigir_sin_trazo()
        return self.history.redo()

    def export(self, ruta: str | Path, ajustes: ExportSettings, limpiar_color: bool) -> Path:
        rgb = decontaminate(self.doc.rgb, self.alpha) if limpiar_color else self.doc.rgb
        return save(compose(rgb, self.alpha, ajustes), ruta, ajustes, self.doc.icc_profile)

    def _aplicar(self, x: float, y: float) -> Rect | None:
        rect = footprint_rect(x, y, self._huella, self.alpha.shape)
        if rect is None:
            return None
        if self._modo is Modo.REFINAR:
            x0, y0, x1, y1 = rect
            self._pintado[y0:y1, x0:x1] |= huella_en(x, y, self._huella, rect) > 0
            return rect
        self.history.touch(*rect)
        return stamp(self.alpha, x, y, self._huella, self._modo)

    def _exigir_sin_trazo(self) -> None:
        if self.trazo_abierto:
            raise RuntimeError("Hay un trazo en curso")
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `10 passed`.

**Paso 5 - Fronteras:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_boundaries.py -q
```
Esperado: `passed` para `core/history.py`, `core/brush.py`, `pipeline/refine_region.py` y
`pipeline/session.py`, sin fallos.

**Commit:**
```powershell
git add src/image_studio/pipeline/session.py tests/pipeline/test_session.py
git commit -m "feat(pipeline): agregar sesion de edicion con pinceles e historial"
```

---

## Fase C - Puentes Qt y tareas en segundo plano

### Tarea 7: buffers numpy para QImage

**Archivos:** crear `src/image_studio/ui/__init__.py`, `src/image_studio/ui/qt_image.py`,
`tests/ui/test_qt_image.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage

from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer, qimage_to_arrays


def test_buffer_rgba_refleja_cambios_sin_copiar(qapp):
    rgb = np.zeros((4, 6, 3), np.uint8)
    rgb[...] = (200, 10, 20)
    alfa = np.ones((4, 6), np.float32)
    buffer = RgbaBuffer(rgb, alfa)
    assert buffer.imagen.pixelColor(1, 1) == QColor(200, 10, 20, 255)
    alfa[1, 1] = 0.0
    buffer.update(rgb, alfa, (0, 0, 2, 2))
    assert buffer.imagen.pixelColor(1, 1).alpha() == 0
    assert buffer.imagen.pixelColor(5, 3).alpha() == 255


def test_buffer_rgb(qapp):
    rgb = np.zeros((3, 5, 3), np.uint8)
    rgb[2, 4] = (1, 2, 3)
    assert RgbBuffer(rgb).imagen.pixelColor(4, 2) == QColor(1, 2, 3)


def test_qimage_a_arreglos_con_alfa(qapp):
    imagen = QImage(5, 3, QImage.Format.Format_ARGB32)
    imagen.fill(QColor(10, 20, 30, 128))
    rgb, alfa = qimage_to_arrays(imagen)
    assert rgb.shape == (3, 5, 3) and tuple(rgb[0, 0]) == (10, 20, 30)
    assert alfa.dtype == np.float32 and alfa[0, 0] == pytest.approx(128 / 255)


def test_qimage_opaca_no_tiene_alfa(qapp):
    imagen = QImage(5, 3, QImage.Format.Format_RGB32)
    imagen.fill(QColor(1, 2, 3))
    rgb, alfa = qimage_to_arrays(imagen)
    assert alfa is None and tuple(rgb[2, 4]) == (1, 2, 3)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_qt_image.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/ui/__init__.py` y
`src/image_studio/ui/qt_image.py`:
```python
"""Puentes entre arreglos numpy y QImage."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage

from image_studio.core.brush import Rect


def _alfa8(alpha: np.ndarray) -> np.ndarray:
    return np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)


class RgbaBuffer:
    """Arreglo RGBA que respalda un QImage sin copia: actualizar el arreglo actualiza la imagen."""

    def __init__(self, rgb: np.ndarray, alpha: np.ndarray):
        alto, ancho = alpha.shape
        self.datos = np.empty((alto, ancho, 4), np.uint8)
        self.datos[..., :3] = rgb
        self.datos[..., 3] = _alfa8(alpha)
        self.imagen = QImage(self.datos.data, ancho, alto, ancho * 4, QImage.Format.Format_RGBA8888)

    def update(self, rgb: np.ndarray, alpha: np.ndarray, rect: Rect) -> None:
        x0, y0, x1, y1 = rect
        self.datos[y0:y1, x0:x1, :3] = rgb[y0:y1, x0:x1]
        self.datos[y0:y1, x0:x1, 3] = _alfa8(alpha[y0:y1, x0:x1])


class RgbBuffer:
    """QImage opaco sobre un arreglo RGB, para la vista del original."""

    def __init__(self, rgb: np.ndarray):
        self.datos = np.ascontiguousarray(rgb)
        alto, ancho = self.datos.shape[:2]
        self.imagen = QImage(self.datos.data, ancho, alto, ancho * 3, QImage.Format.Format_RGB888)


def qimage_to_arrays(imagen: QImage) -> tuple[np.ndarray, np.ndarray | None]:
    """RGB uint8 y alfa float32 (None si es opaca) a partir de cualquier QImage."""
    rgba = imagen.convertToFormat(QImage.Format.Format_RGBA8888)
    alto, ancho = rgba.height(), rgba.width()
    crudo = np.frombuffer(rgba.constBits(), np.uint8, count=rgba.sizeInBytes())
    pixeles = crudo.reshape(alto, rgba.bytesPerLine())[:, : ancho * 4].reshape(alto, ancho, 4).copy()
    alfa = pixeles[..., 3]
    rgb = np.ascontiguousarray(pixeles[..., :3])
    if (alfa == 255).all():
        return rgb, None
    return rgb, alfa.astype(np.float32) / 255.0
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/__init__.py src/image_studio/ui/qt_image.py tests/ui/test_qt_image.py
git commit -m "feat(ui): respaldar qimage con buffers numpy sin copia"
```

### Tarea 8: tareas en segundo plano

**Archivos:** crear `src/image_studio/workers/__init__.py`, `src/image_studio/workers/tasks.py`,
`tests/workers/test_tasks.py`

**Paso 1 - Tests que fallan:**
```python
import threading

from image_studio.workers.tasks import ejecutar


def test_devuelve_el_resultado_en_el_hilo_principal(qtbot):
    recibidos, hilos = [], []

    def sumar(a, b):
        hilos.append(threading.current_thread())
        return a + b

    ejecutar(sumar, 2, 3, al_terminar=recibidos.append, al_fallar=recibidos.append)
    qtbot.waitUntil(lambda: recibidos == [5])
    assert hilos[0] is not threading.main_thread()


def test_reporta_el_error(qtbot):
    errores = []

    def fallar():
        raise ValueError("malo")

    ejecutar(fallar, al_terminar=errores.append, al_fallar=errores.append)
    qtbot.waitUntil(lambda: bool(errores))
    assert errores == ["ValueError: malo"]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/workers/test_tasks.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.workers'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/workers/__init__.py` y
`src/image_studio/workers/tasks.py`:
```python
"""Ejecutar funciones en el QThreadPool y recibir el resultado en el hilo principal."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Senales(QObject):
    listo = Signal(object)
    fallo = Signal(str)


class Tarea(QRunnable):
    def __init__(self, funcion: Callable, *args):
        super().__init__()
        self.funcion = funcion
        self.args = args
        self.senales = _Senales()

    def run(self) -> None:
        try:
            resultado = self.funcion(*self.args)
        except Exception as exc:  # el error se muestra en la interfaz, no se pierde en el hilo
            self.senales.fallo.emit(f"{type(exc).__name__}: {exc}")
            return
        self.senales.listo.emit(resultado)


# Referencias vivas hasta que la tarea avisa; sin ellas Python puede destruir las señales antes.
_activas: set[Tarea] = set()


def ejecutar(
    funcion: Callable,
    *args,
    al_terminar: Callable[[object], None],
    al_fallar: Callable[[str], None],
    pool: QThreadPool | None = None,
) -> Tarea:
    tarea = Tarea(funcion, *args)
    _activas.add(tarea)
    tarea.senales.listo.connect(lambda resultado: (_activas.discard(tarea), al_terminar(resultado)))
    tarea.senales.fallo.connect(lambda mensaje: (_activas.discard(tarea), al_fallar(mensaje)))
    (pool or QThreadPool.globalInstance()).start(tarea)
    return tarea
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `2 passed`.

**Commit:**
```powershell
git add src/image_studio/workers/__init__.py src/image_studio/workers/tasks.py tests/workers/test_tasks.py
git commit -m "feat(workers): ejecutar tareas en segundo plano con senales qt"
```

---

## Fase D - Lienzo

### Tarea 9: capa de imagen

**Archivos:** crear `src/image_studio/ui/canvas/__init__.py`, `src/image_studio/ui/canvas/layer.py`,
`tests/ui/test_layer.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsScene

from image_studio.ui.canvas.layer import ImageLayer
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer


def _render(escena: QGraphicsScene) -> QImage:
    destino = QImage(10, 10, QImage.Format.Format_ARGB32)
    destino.fill(QColor(255, 255, 255))
    pintor = QPainter(destino)
    escena.render(pintor, QRectF(0, 0, 10, 10), QRectF(0, 0, 10, 10))
    pintor.end()
    return destino


def _capa():
    rgb = np.zeros((10, 10, 3), np.uint8)
    rgb[...] = (255, 0, 0)
    alfa = np.zeros((10, 10), np.float32)
    alfa[:, 5:] = 1.0
    despues, antes = RgbaBuffer(rgb, alfa), RgbBuffer(rgb)
    capa = ImageLayer()
    capa.set_images(despues.imagen, antes.imagen)
    escena = QGraphicsScene()
    escena.addItem(capa)
    return capa, escena, (despues, antes)


def test_sin_imagen_no_ocupa_espacio(qapp):
    assert ImageLayer().boundingRect().isEmpty()


def test_dibuja_el_recorte_con_transparencia(qapp):
    capa, escena, _buffers = _capa()
    assert capa.boundingRect() == QRectF(0, 0, 10, 10)
    imagen = _render(escena)
    assert imagen.pixelColor(2, 5) == QColor(255, 255, 255)
    assert imagen.pixelColor(8, 5) == QColor(255, 0, 0)


def test_antes_muestra_el_original(qapp):
    capa, escena, _buffers = _capa()
    capa.set_show_before(True)
    assert capa.mostrando_antes
    assert _render(escena).pixelColor(2, 5) == QColor(255, 0, 0)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_layer.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.canvas'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/ui/canvas/__init__.py` y
`src/image_studio/ui/canvas/layer.py`:
```python
"""Capa que dibuja el recorte (o el original) leyendo directo del buffer numpy."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem


class ImageLayer(QGraphicsItem):
    def __init__(self):
        super().__init__()
        # exposedRect permite dibujar solo la zona visible o actualizada.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self._despues: QImage | None = None
        self._antes: QImage | None = None
        self._mostrar_antes = False

    @property
    def mostrando_antes(self) -> bool:
        return self._mostrar_antes

    def set_images(self, despues: QImage, antes: QImage) -> None:
        self.prepareGeometryChange()
        self._despues = despues
        self._antes = antes
        self.update()

    def set_show_before(self, valor: bool) -> None:
        self._mostrar_antes = valor
        self.update()

    def boundingRect(self) -> QRectF:
        if self._despues is None:
            return QRectF()
        return QRectF(0, 0, self._despues.width(), self._despues.height())

    def paint(self, painter: QPainter, option, widget=None) -> None:
        imagen = self._antes if self._mostrar_antes else self._despues
        if imagen is None:
            return
        expuesta = option.exposedRect
        zona = (expuesta if expuesta.isValid() and not expuesta.isEmpty() else self.boundingRect())
        zona = zona.intersected(self.boundingRect())
        if zona.isEmpty():
            return
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, painter.worldTransform().m11() < 1.0
        )
        painter.drawImage(zona, imagen, zona)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/canvas/__init__.py src/image_studio/ui/canvas/layer.py tests/ui/test_layer.py
git commit -m "feat(ui): dibujar recorte y original desde el buffer"
```

### Tarea 10: vista del lienzo

**Archivos:** crear `src/image_studio/ui/canvas/view.py`, `tests/ui/test_view.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer


def _evento(tipo, x, y, boton, botones):
    punto = QPointF(x, y)
    return QMouseEvent(tipo, punto, punto, boton, botones, Qt.KeyboardModifier.NoModifier)


@pytest.fixture
def vista(qtbot):
    vista = CanvasView()
    qtbot.addWidget(vista)
    vista.resize(400, 300)
    vista.show()
    rgb = np.zeros((100, 200, 3), np.uint8)
    vista._buffers = (RgbaBuffer(rgb, np.ones((100, 200), np.float32)), RgbBuffer(rgb))
    vista.set_images(vista._buffers[0].imagen, vista._buffers[1].imagen)
    return vista


def test_ajustar_encaja_la_imagen(vista):
    assert 1.5 < vista.escala < 2.1


def test_zoom_respeta_limites(vista):
    vista.zoom(1000)
    assert vista.escala == pytest.approx(CanvasView.ESCALA_MAX)
    vista.zoom(1e-6)
    assert vista.escala == pytest.approx(CanvasView.ESCALA_MIN)


def test_trazo_emite_coordenadas_de_la_imagen(vista):
    eventos = []
    vista.trazo_inicio.connect(lambda p: eventos.append(("inicio", p)))
    vista.trazo_mueve.connect(lambda p: eventos.append(("mueve", p)))
    vista.trazo_fin.connect(lambda: eventos.append(("fin", None)))
    vista.pintura_habilitada = True
    centro = vista.viewport().rect().center()
    izq = Qt.MouseButton.LeftButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, centro.x(), centro.y(), izq, izq))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseMove, centro.x() + 20, centro.y(), Qt.MouseButton.NoButton, izq))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonRelease, centro.x() + 20, centro.y(), izq, Qt.MouseButton.NoButton))
    assert [e[0] for e in eventos] == ["inicio", "mueve", "fin"]
    inicio = eventos[0][1]
    assert abs(inicio.x() - 100) < 2 and abs(inicio.y() - 50) < 2
    assert eventos[1][1].x() > inicio.x()


def test_sin_pintura_habilitada_no_emite(vista):
    eventos = []
    vista.trazo_inicio.connect(eventos.append)
    izq = Qt.MouseButton.LeftButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, 200, 150, izq, izq))
    assert eventos == []


def test_boton_central_desplaza(vista):
    vista.zoom(4)
    barra = vista.horizontalScrollBar()
    barra.setValue(barra.maximum() // 2)
    antes = barra.value()
    medio = Qt.MouseButton.MiddleButton
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonPress, 200, 150, medio, medio))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseMove, 150, 150, Qt.MouseButton.NoButton, medio))
    QApplication.sendEvent(vista.viewport(), _evento(QEvent.Type.MouseButtonRelease, 150, 150, medio, Qt.MouseButton.NoButton))
    assert barra.value() == antes + 50


def test_vista_previa_de_refinar(vista):
    vista.iniciar_vista_refinar(10, QPointF(10, 10))
    vista.agregar_punto_refinar(QPointF(50, 10))
    assert not vista.ruta_refinar.isEmpty()
    vista.limpiar_vista_refinar()
    assert vista.ruta_refinar.isEmpty()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_view.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.canvas.view'`.

**Paso 3 - Implementar** `src/image_studio/ui/canvas/view.py`:
```python
"""Lienzo: tablero de transparencia, zoom, desplazamiento y trazos de pincel."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from image_studio.core.brush import Rect
from image_studio.ui.canvas.layer import ImageLayer

FONDO_VISTA = QColor(45, 45, 48)


def _patron_ajedrez(lado: int = 8) -> QBrush:
    imagen = QImage(2 * lado, 2 * lado, QImage.Format.Format_RGB32)
    imagen.fill(QColor(204, 204, 204))
    pintor = QPainter(imagen)
    pintor.fillRect(0, 0, lado, lado, QColor(153, 153, 153))
    pintor.fillRect(lado, lado, lado, lado, QColor(153, 153, 153))
    pintor.end()
    return QBrush(imagen)


class CanvasView(QGraphicsView):
    trazo_inicio = Signal(QPointF)
    trazo_mueve = Signal(QPointF)
    trazo_fin = Signal()
    ESCALA_MIN = 0.02
    ESCALA_MAX = 32.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.capa = ImageLayer()
        self.scene().addItem(self.capa)
        self._cursor = QGraphicsEllipseItem()
        pluma = QPen(QColor(255, 255, 255))
        pluma.setCosmetic(True)
        self._cursor.setPen(pluma)
        self._cursor.setZValue(10)
        self._cursor.hide()
        self.scene().addItem(self._cursor)
        self.ruta_refinar = QPainterPath()
        self._vista_refinar = QGraphicsPathItem()
        self._vista_refinar.setZValue(5)
        self.scene().addItem(self._vista_refinar)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # El tablero está fijo a la pantalla, así que hay que repintar todo al desplazar.
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)
        self.pintura_habilitada = False
        self._radio = 30.0
        self._pintando = False
        self._paneo: QPointF | None = None
        self._ajedrez = _patron_ajedrez()

    @property
    def escala(self) -> float:
        return self.transform().m11()

    def set_images(self, despues: QImage, antes: QImage) -> None:
        self.capa.set_images(despues, antes)
        self.scene().setSceneRect(self.capa.boundingRect())
        self.ajustar()

    def ajustar(self) -> None:
        if not self.capa.boundingRect().isEmpty():
            self.fitInView(self.capa, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_real(self) -> None:
        self.resetTransform()

    def zoom(self, factor: float) -> None:
        objetivo = min(max(self.escala * factor, self.ESCALA_MIN), self.ESCALA_MAX)
        relativo = objetivo / self.escala
        self.scale(relativo, relativo)

    def actualizar(self, rect: Rect) -> None:
        x0, y0, x1, y1 = rect
        self.capa.update(QRectF(x0, y0, x1 - x0, y1 - y0))

    def set_brush_radius(self, radio: float) -> None:
        self._radio = radio
        self._mover_cursor(self._cursor.rect().center())

    def iniciar_vista_refinar(self, radio: float, punto: QPointF) -> None:
        pluma = QPen(QColor(255, 0, 170, 110), 2 * radio)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._vista_refinar.setPen(pluma)
        self.ruta_refinar = QPainterPath(punto)
        self.ruta_refinar.lineTo(punto)
        self._vista_refinar.setPath(self.ruta_refinar)

    def agregar_punto_refinar(self, punto: QPointF) -> None:
        self.ruta_refinar.lineTo(punto)
        self._vista_refinar.setPath(self.ruta_refinar)

    def limpiar_vista_refinar(self) -> None:
        self.ruta_refinar = QPainterPath()
        self._vista_refinar.setPath(self.ruta_refinar)

    def wheelEvent(self, evento) -> None:
        pasos = evento.angleDelta().y() / 120
        if pasos:
            self.zoom(1.25**pasos)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.MiddleButton:
            self._paneo = evento.position()
            return
        if (
            evento.button() == Qt.MouseButton.LeftButton
            and self.pintura_habilitada
            and not self.capa.boundingRect().isEmpty()
        ):
            self._pintando = True
            self.trazo_inicio.emit(self.mapToScene(evento.position().toPoint()))
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:
        punto = self.mapToScene(evento.position().toPoint())
        self._mover_cursor(punto)
        if self._paneo is not None:
            delta = evento.position() - self._paneo
            self._paneo = evento.position()
            barra_h, barra_v = self.horizontalScrollBar(), self.verticalScrollBar()
            barra_h.setValue(barra_h.value() - int(delta.x()))
            barra_v.setValue(barra_v.value() - int(delta.y()))
            return
        if self._pintando:
            self.trazo_mueve.emit(punto)
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.MiddleButton:
            self._paneo = None
            return
        if evento.button() == Qt.MouseButton.LeftButton and self._pintando:
            self._pintando = False
            self.trazo_fin.emit()
            return
        super().mouseReleaseEvent(evento)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.resetTransform()
        painter.fillRect(self.viewport().rect(), FONDO_VISTA)
        if not self.capa.boundingRect().isEmpty():
            zona = self.mapFromScene(self.capa.boundingRect()).boundingRect()
            painter.fillRect(zona, self._ajedrez)
        painter.restore()

    def _mover_cursor(self, centro: QPointF) -> None:
        r = self._radio
        self._cursor.setRect(centro.x() - r, centro.y() - r, 2 * r, 2 * r)
        self._cursor.setVisible(self.pintura_habilitada)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/canvas/view.py tests/ui/test_view.py
git commit -m "feat(ui): agregar lienzo con zoom, desplazamiento y trazos"
```

---

## Fase E - Ventana

### Tarea 11: ventana principal

**Archivos:** crear `src/image_studio/ui/main_window.py`, `tests/ui/test_main_window.py`

**Paso 1 - Tests que fallan:**
```python
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.ui.main_window import MainWindow


class RemovedorFijo:
    def run(self, doc, ajustes, usar_alfa_existente=False):
        alfa = np.zeros(doc.rgb.shape[:2], np.float32)
        alfa[20:80, 20:80] = 1.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.01})


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


@pytest.fixture
def ventana(qtbot):
    ventana = MainWindow(crear_removedor=lambda modelo, dispositivo, progreso: RemovedorFijo(), matter=MatterFijo())
    qtbot.addWidget(ventana)
    ventana.resize(800, 600)
    ventana.show()
    return ventana


@pytest.fixture
def abierta(ventana, escribir_png, tmp_path):
    assert ventana.abrir(escribir_png(tmp_path / "foto.png", ancho=100, alto=100))
    return ventana


def _trazo(ventana, desde, hasta):
    ventana._trazo_inicio(QPointF(*desde))
    ventana._trazo_mueve(QPointF(*hasta))
    ventana._trazo_fin()


def test_estado_inicial(ventana):
    assert ventana.sesion is None
    assert not ventana.accion_quitar.isEnabled() and ventana.accion_abrir.isEnabled()


def test_abrir_imagen(abierta):
    assert abierta.sesion.doc.size == (100, 100)
    assert "foto.png" in abierta.windowTitle()
    assert abierta.accion_quitar.isEnabled()


def test_archivo_corrupto_muestra_error(ventana, tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"x")
    assert not ventana.abrir(ruta)
    assert "No se pudo leer" in ventana.statusBar().currentMessage()
    assert ventana.sesion is None


def test_quitar_fondo_en_segundo_plano(abierta, qtbot):
    abierta.quitar_fondo()
    assert abierta.ocupado
    qtbot.waitUntil(lambda: not abierta.ocupado)
    assert abierta.sesion.alpha[50, 50] == 1.0 and abierta.sesion.alpha[0, 0] == 0.0
    assert "Fondo quitado" in abierta.statusBar().currentMessage()


def test_sin_herramienta_no_pinta(abierta):
    _trazo(abierta, (50, 50), (60, 50))
    assert (abierta.sesion.alpha == 1.0).all()


def test_borrar_y_deshacer(abierta):
    abierta.accion_borrar.trigger()
    abierta.spin_radio.setValue(5)
    abierta.spin_dureza.setValue(100)
    _trazo(abierta, (50, 50), (60, 50))
    assert abierta.sesion.alpha[50, 55] == 0.0
    assert abierta.accion_deshacer.isEnabled()
    abierta.deshacer()
    assert (abierta.sesion.alpha == 1.0).all()
    abierta.rehacer()
    assert abierta.sesion.alpha[50, 55] == 0.0


def test_refinar_corre_en_segundo_plano(abierta, qtbot):
    abierta.accion_refinar.trigger()
    abierta.spin_radio.setValue(5)
    _trazo(abierta, (50, 50), (60, 50))
    qtbot.waitUntil(lambda: not abierta.ocupado)
    assert abierta.sesion.alpha[50, 55] == pytest.approx(0.42)
    assert abierta.lienzo.ruta_refinar.isEmpty()
    abierta.deshacer()
    assert (abierta.sesion.alpha == 1.0).all()


def test_guardar_png(abierta, qtbot, tmp_path):
    abierta.quitar_fondo()
    qtbot.waitUntil(lambda: not abierta.ocupado)
    destino = abierta.guardar_en(tmp_path / "salida.png")
    with Image.open(destino) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[50, 50] == 255


def test_pegar_desde_portapapeles(ventana):
    imagen = QImage(30, 20, QImage.Format.Format_RGBA8888)
    imagen.fill(QColor(10, 20, 30, 255))
    QApplication.clipboard().setImage(imagen)
    ventana.pegar()
    assert ventana.sesion.doc.size == (30, 20)


def test_ver_original(abierta):
    abierta.accion_antes.trigger()
    assert abierta.lienzo.capa.mostrando_antes
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_main_window.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.main_window'`.

**Paso 3 - Implementar** `src/image_studio/ui/main_window.py`:
```python
"""Ventana principal del editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QThreadPool
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QSpinBox,
    QToolBar,
)

from image_studio.core.brush import Modo, Rect
from image_studio.core.export import ExportSettings
from image_studio.core.image_io import FORMATOS_ENTRADA, ImageDoc, ImageLoadError, load_image
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.factory import build_remover
from image_studio.pipeline.session import EditSession, Pincel
from image_studio.pipeline.settings import PRESETS
from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer, qimage_to_arrays
from image_studio.workers.tasks import ejecutar

FILTRO_IMAGENES = "Imágenes (" + " ".join(f"*{e}" for e in sorted(FORMATOS_ENTRADA)) + ")"


class MainWindow(QMainWindow):
    def __init__(self, crear_removedor=build_remover, matter=None):
        super().__init__()
        self.setWindowTitle("Image Studio")
        self.resize(1400, 900)
        self.setAcceptDrops(True)
        self._crear_removedor = crear_removedor
        self._removedores: dict[str, object] = {}
        self._matter = matter if matter is not None else ClassicMatter()
        self.sesion: EditSession | None = None
        self._despues: RgbaBuffer | None = None
        self._antes: RgbBuffer | None = None
        self.ocupado = False
        self.lienzo = CanvasView(self)
        self.setCentralWidget(self.lienzo)
        self.lienzo.trazo_inicio.connect(self._trazo_inicio)
        self.lienzo.trazo_mueve.connect(self._trazo_mueve)
        self.lienzo.trazo_fin.connect(self._trazo_fin)
        self._crear_interfaz()
        self._actualizar_estado()
        self.statusBar().showMessage("Abre una imagen (Ctrl+O), arrástrala aquí o pégala (Ctrl+V)")

    # Interfaz

    def _accion(self, texto: str, atajos: list[str], funcion, marcable: bool = False) -> QAction:
        accion = QAction(texto, self)
        accion.setShortcuts([QKeySequence(a) for a in atajos])
        accion.setCheckable(marcable)
        accion.triggered.connect(funcion)
        self.addAction(accion)
        return accion

    def _crear_interfaz(self) -> None:
        self.accion_abrir = self._accion("Abrir...", ["Ctrl+O"], lambda *_: self._abrir_dialogo())
        self.accion_pegar = self._accion("Pegar", ["Ctrl+V"], lambda *_: self.pegar())
        self.accion_guardar = self._accion("Guardar PNG...", ["Ctrl+S"], lambda *_: self._guardar_dialogo())
        self.accion_quitar = self._accion("Quitar fondo", ["Ctrl+R"], lambda *_: self.quitar_fondo())
        self.accion_deshacer = self._accion("Deshacer", ["Ctrl+Z"], lambda *_: self.deshacer())
        self.accion_rehacer = self._accion("Rehacer", ["Ctrl+Y", "Ctrl+Shift+Z"], lambda *_: self.rehacer())
        self.accion_antes = self._accion(
            "Ver original", ["B"], lambda marcado: self.lienzo.capa.set_show_before(marcado), marcable=True
        )
        self.accion_ajustar = self._accion("Ajustar", ["Ctrl+0"], lambda *_: self.lienzo.ajustar())
        self.accion_100 = self._accion("100%", ["Ctrl+1"], lambda *_: self.lienzo.zoom_real())

        grupo = QActionGroup(self)
        self._herramientas: list[tuple[QAction, Modo | None]] = []
        for texto, atajo, modo in (
            ("Mover", "V", None),
            ("Conservar", "K", Modo.CONSERVAR),
            ("Borrar", "E", Modo.BORRAR),
            ("Refinar borde", "R", Modo.REFINAR),
        ):
            accion = self._accion(texto, [atajo], lambda *_: self._actualizar_estado(), marcable=True)
            grupo.addAction(accion)
            self._herramientas.append((accion, modo))
        self.accion_mover, self.accion_conservar, self.accion_borrar, self.accion_refinar = (
            a for a, _ in self._herramientas
        )
        self.accion_mover.setChecked(True)

        self.combo_preset = QComboBox()
        self.combo_preset.addItems(sorted(PRESETS))
        self.combo_preset.setCurrentText("producto")
        self.spin_radio = QSpinBox()
        self.spin_radio.setRange(1, 500)
        self.spin_radio.setValue(30)
        self.spin_radio.valueChanged.connect(lambda valor: self.lienzo.set_brush_radius(float(valor)))
        self.spin_dureza = QSpinBox()
        self.spin_dureza.setRange(0, 100)
        self.spin_dureza.setValue(80)
        self.spin_dureza.setSuffix(" %")

        barra = QToolBar("Herramientas")
        barra.setMovable(False)
        self.addToolBar(barra)
        for accion in (self.accion_abrir, self.accion_pegar, self.accion_guardar):
            barra.addAction(accion)
        barra.addSeparator()
        barra.addWidget(QLabel(" Preset "))
        barra.addWidget(self.combo_preset)
        barra.addAction(self.accion_quitar)
        barra.addSeparator()
        for accion, _ in self._herramientas:
            barra.addAction(accion)
        barra.addWidget(QLabel(" Radio "))
        barra.addWidget(self.spin_radio)
        barra.addWidget(QLabel(" Dureza "))
        barra.addWidget(self.spin_dureza)
        barra.addSeparator()
        for accion in (self.accion_deshacer, self.accion_rehacer, self.accion_antes, self.accion_ajustar, self.accion_100):
            barra.addAction(accion)

    def _modo_actual(self) -> Modo | None:
        return next((modo for accion, modo in self._herramientas if accion.isChecked()), None)

    def _actualizar_estado(self) -> None:
        hay = self.sesion is not None
        libre = not self.ocupado
        editable = hay and libre
        for accion in (self.accion_abrir, self.accion_pegar):
            accion.setEnabled(libre)
        for accion in (self.accion_guardar, self.accion_quitar, self.accion_antes, self.accion_ajustar, self.accion_100):
            accion.setEnabled(editable)
        for accion, _ in self._herramientas:
            accion.setEnabled(editable)
        sin_trazo = editable and not self.sesion.trazo_abierto
        self.accion_deshacer.setEnabled(sin_trazo and self.sesion.history.puede_deshacer)
        self.accion_rehacer.setEnabled(sin_trazo and self.sesion.history.puede_rehacer)
        self.lienzo.pintura_habilitada = editable and self._modo_actual() is not None
        self.lienzo.set_brush_radius(float(self.spin_radio.value()))

    def _ocupar(self, mensaje: str) -> None:
        self.ocupado = True
        self.statusBar().showMessage(mensaje)
        self._actualizar_estado()

    def _liberar(self) -> None:
        self.ocupado = False
        self._actualizar_estado()

    def _refrescar(self, rect: Rect | None) -> None:
        if rect is None or self._despues is None:
            return
        self._despues.update(self.sesion.rgb, self.sesion.alpha, rect)
        self.lienzo.actualizar(rect)

    # Abrir

    def abrir(self, ruta: str | Path) -> bool:
        try:
            doc = load_image(ruta)
        except ImageLoadError as exc:
            self.statusBar().showMessage(str(exc))
            return False
        return self.cargar_doc(doc)

    def cargar_doc(self, doc: ImageDoc) -> bool:
        if self.ocupado:
            self.statusBar().showMessage("Espera a que termine la tarea en curso")
            return False
        self.sesion = EditSession(doc)
        self._despues = RgbaBuffer(self.sesion.rgb, self.sesion.alpha)
        self._antes = RgbBuffer(doc.rgb)
        self.lienzo.set_images(self._despues.imagen, self._antes.imagen)
        self.accion_antes.setChecked(False)
        self.lienzo.capa.set_show_before(False)
        self.setWindowTitle(f"{doc.path.name} - Image Studio")
        ancho, alto = doc.size
        self.statusBar().showMessage(f"{doc.path.name}: {ancho}x{alto}")
        self._actualizar_estado()
        return True

    def cargar_qimage(self, imagen: QImage, nombre: str = "portapapeles.png") -> bool:
        rgb, alfa = qimage_to_arrays(imagen)
        return self.cargar_doc(ImageDoc(Path(nombre), rgb, alfa, None, None))

    def pegar(self) -> None:
        imagen = QApplication.clipboard().image()
        if imagen.isNull():
            self.statusBar().showMessage("El portapapeles no tiene una imagen")
            return
        self.cargar_qimage(imagen)

    def _abrir_dialogo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir imagen", "", FILTRO_IMAGENES)
        if ruta:
            self.abrir(Path(ruta))

    def dragEnterEvent(self, evento) -> None:
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:
        rutas = [Path(url.toLocalFile()) for url in evento.mimeData().urls() if url.isLocalFile()]
        if rutas:
            self.abrir(rutas[0])

    # Quitar fondo

    def quitar_fondo(self) -> None:
        if self.sesion is None or self.ocupado:
            return
        nombre = self.combo_preset.currentText()
        self._ocupar(f"Quitando fondo ({nombre})...")
        ejecutar(
            self._ejecutar_removedor,
            self.sesion.doc,
            PRESETS[nombre],
            al_terminar=self._fondo_quitado,
            al_fallar=self._tarea_fallida,
        )

    def _ejecutar_removedor(self, doc, ajustes):
        # Corre en un hilo de trabajo; la primera vez carga el modelo (BiRefNet tarda unos 11 s).
        removedor = self._removedores.get(ajustes.modelo)
        if removedor is None:
            removedor = self._crear_removedor(ajustes.modelo, "auto", None)
            self._removedores[ajustes.modelo] = removedor
        return removedor.run(doc, ajustes)

    def _fondo_quitado(self, resultado) -> None:
        self._liberar()
        self._refrescar(self.sesion.apply_result(resultado))
        self._actualizar_estado()
        total = sum(resultado.tiempos.values())
        aviso = f" Revisar: {resultado.motivo_confianza}." if resultado.baja_confianza else ""
        self.statusBar().showMessage(f"Fondo quitado en {total:.1f} s.{aviso}")

    def _tarea_fallida(self, mensaje: str) -> None:
        if self.sesion is not None and self.sesion.refinado_pendiente:
            self.sesion.cancel_refine()
            self.lienzo.limpiar_vista_refinar()
        self._liberar()
        self.statusBar().showMessage(f"Error: {mensaje}")

    # Pinceles

    def _trazo_inicio(self, punto: QPointF) -> None:
        modo = self._modo_actual()
        if self.sesion is None or self.ocupado or modo is None:
            return
        self.sesion.pincel = Pincel(modo, float(self.spin_radio.value()), self.spin_dureza.value() / 100)
        if modo is Modo.REFINAR:
            self.lienzo.iniciar_vista_refinar(self.sesion.pincel.radio, punto)
        self._refrescar(self.sesion.begin_stroke(punto.x(), punto.y()))

    def _trazo_mueve(self, punto: QPointF) -> None:
        if self.sesion is None or self.ocupado or not self.sesion.trazo_abierto:
            return
        if self.sesion.pincel.modo is Modo.REFINAR:
            self.lienzo.agregar_punto_refinar(punto)
        self._refrescar(self.sesion.move_stroke(punto.x(), punto.y()))

    def _trazo_fin(self) -> None:
        if self.sesion is None or self.ocupado:
            return
        self.sesion.end_stroke()
        if self.sesion.refinado_pendiente:
            self._ocupar("Refinando borde...")
            ejecutar(
                self.sesion.refine_pending,
                self._matter,
                al_terminar=self._borde_refinado,
                al_fallar=self._tarea_fallida,
            )
            return
        self._actualizar_estado()

    def _borde_refinado(self, rect: Rect | None) -> None:
        self.lienzo.limpiar_vista_refinar()
        self._liberar()
        self._refrescar(rect)
        self.statusBar().showMessage("Borde refinado")

    # Historial y guardado

    def deshacer(self) -> None:
        if self.sesion is None or self.ocupado or self.sesion.trazo_abierto:
            return
        for rect in self.sesion.undo():
            self._refrescar(rect)
        self._actualizar_estado()

    def rehacer(self) -> None:
        if self.sesion is None or self.ocupado or self.sesion.trazo_abierto:
            return
        for rect in self.sesion.redo():
            self._refrescar(rect)
        self._actualizar_estado()

    def _guardar_dialogo(self) -> None:
        if self.sesion is None:
            return
        sugerido = str(self.sesion.doc.path.with_suffix(".png"))
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar PNG", sugerido, "PNG (*.png)")
        if ruta:
            self.guardar_en(Path(ruta))

    def guardar_en(self, ruta: Path) -> Path | None:
        if self.sesion is None or self.ocupado:
            return None
        limpiar = self.sesion.resultado is not None and PRESETS[self.combo_preset.currentText()].limpieza_color
        destino = self.sesion.export(ruta, ExportSettings(), limpiar_color=limpiar)
        self.statusBar().showMessage(f"Guardado: {destino}")
        return destino

    def closeEvent(self, evento) -> None:
        # Un hilo de trabajo vivo al cerrar Python puede terminar el proceso con error.
        QThreadPool.globalInstance().waitForDone()
        super().closeEvent(evento)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `11 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/main_window.py tests/ui/test_main_window.py
git commit -m "feat(ui): agregar ventana del editor con pinceles e historial"
```

### Tarea 12: arranque de la aplicación y tema

**Archivos:** crear `src/image_studio/ui/app.py`, `tests/ui/test_app.py`

**Paso 1 - Tests que fallan:**
```python
from PySide6.QtGui import QPalette

from image_studio.ui.app import FONDO_VENTANA, aplicar_tema, crear_ventana


def test_tema_oscuro(qapp):
    aplicar_tema(qapp)
    assert qapp.style().name().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window) == FONDO_VENTANA


def test_crear_ventana_abre_la_imagen_indicada(qtbot, escribir_png, tmp_path):
    ventana = crear_ventana([str(escribir_png(tmp_path / "a.png"))])
    qtbot.addWidget(ventana)
    assert ventana.sesion is not None


def test_crear_ventana_sin_imagen(qtbot):
    ventana = crear_ventana([])
    qtbot.addWidget(ventana)
    assert ventana.sesion is None
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_app.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.app'`.

**Paso 3 - Implementar** `src/image_studio/ui/app.py`:
```python
"""Arranque de la interfaz gráfica y tema oscuro."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from image_studio.ui.main_window import MainWindow

FONDO_VENTANA = QColor(53, 53, 57)
FONDO_CAMPOS = QColor(37, 37, 40)
TEXTO = QColor(225, 225, 225)
TEXTO_DESACTIVADO = QColor(120, 120, 120)
ACENTO = QColor(64, 128, 214)


def aplicar_tema(app: QApplication) -> None:
    app.setStyle("Fusion")
    paleta = QPalette()
    rol = QPalette.ColorRole
    for papel, color in (
        (rol.Window, FONDO_VENTANA),
        (rol.WindowText, TEXTO),
        (rol.Base, FONDO_CAMPOS),
        (rol.AlternateBase, FONDO_VENTANA),
        (rol.ToolTipBase, FONDO_VENTANA),
        (rol.ToolTipText, TEXTO),
        (rol.Text, TEXTO),
        (rol.Button, FONDO_VENTANA),
        (rol.ButtonText, TEXTO),
        (rol.Highlight, ACENTO),
        (rol.HighlightedText, QColor(255, 255, 255)),
        (rol.PlaceholderText, TEXTO_DESACTIVADO),
    ):
        paleta.setColor(papel, color)
    for papel in (rol.Text, rol.ButtonText, rol.WindowText):
        paleta.setColor(QPalette.ColorGroup.Disabled, papel, TEXTO_DESACTIVADO)
    app.setPalette(paleta)


def crear_ventana(rutas: list[str]) -> MainWindow:
    ventana = MainWindow()
    if rutas:
        ventana.abrir(Path(rutas[0]))
    return ventana


def run(argv: list[str]) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Image Studio")
    aplicar_tema(app)
    ventana = crear_ventana(argv)
    ventana.show()
    return app.exec()
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/app.py tests/ui/test_app.py
git commit -m "feat(ui): arrancar la aplicacion con tema oscuro"
```

### Tarea 13: abrir el editor con `python -m image_studio`

**Archivos:** modificar `src/image_studio/__main__.py`, `README.md`; crear `tests/test_main.py`

**Paso 1 - Tests que fallan** (`tests/test_main.py`):
```python
import pytest

import image_studio.ui.app
from image_studio.__main__ import principal


def test_batch_va_a_la_cli():
    with pytest.raises(SystemExit) as salida:
        principal(["batch", "--help"])
    assert salida.value.code == 0


def test_sin_argumentos_abre_el_editor(monkeypatch):
    llamadas = []
    monkeypatch.setattr(image_studio.ui.app, "run", lambda argv: llamadas.append(argv) or 0)
    assert principal([]) == 0
    assert principal(["foto.png"]) == 0
    assert llamadas == [[], ["foto.png"]]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_main.py -q
```
Esperado: `ImportError: cannot import name 'principal' from 'image_studio.__main__'`.

**Paso 3 - Implementar.** Reemplazar `src/image_studio/__main__.py` por:
```python
"""python -m image_studio [IMAGEN] abre el editor; python -m image_studio batch ... usa la CLI."""

from __future__ import annotations

import sys

from image_studio.cli import main as cli_main


def principal(argv: list[str]) -> int:
    if argv and argv[0] in ("batch", "-h", "--help"):
        return cli_main(argv)
    from image_studio.ui import app

    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
```

Agregar al final de `README.md`:
````markdown

## Uso (Hito 2: editor)

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio
.\.venv\Scripts\python.exe -X utf8 -m image_studio D:\fotos\termo.jpg
```

Atajos: Ctrl+O abrir, Ctrl+V pegar, Ctrl+R quitar fondo, V mover, K conservar, E borrar,
R refinar borde, Ctrl+Z deshacer, Ctrl+Y rehacer, B ver original, Ctrl+0 ajustar, Ctrl+1 100%,
Ctrl+S guardar PNG. Rueda: zoom. Botón central: desplazar.
````

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_main.py tests/test_cli.py -q
```
Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/__main__.py README.md tests/test_main.py
git commit -m "feat(ui): abrir el editor al ejecutar el paquete sin comando"
```

---

## Fase F - Verificación

### Tarea 14: benchmark de refinar borde (V6)

**Archivos:** modificar `scripts/benchmark.py`

Sin test unitario: medición en el equipo objetivo.

**Paso 1 - Implementar.** En `scripts/benchmark.py`:

1. Reemplazar el bloque de imports desde `import cv2` hasta
   `from image_studio.pipeline.settings import PRESETS` por:
   ```python
   from dataclasses import replace

   import cv2
   import numpy as np

   from image_studio.core.image_io import load_image
   from image_studio.core.mask_ops import DESCONOCIDO, make_trimap
   from image_studio.engines.matting_classic import ClassicMatter
   from image_studio.pipeline.factory import build_remover
   from image_studio.pipeline.refine_region import refine_region, region_bbox
   from image_studio.pipeline.settings import PRESETS
   ```
2. Reemplazar `LIMITE_S = {"auto": 5.0, "cpu": 60.0}` por:
   ```python
   LIMITE_S = {"auto": 5.0, "cpu": 60.0}
   LIMITE_REFINAR_S = 2.0
   LADO_REGION = 500


   def medir_refinado(removedor, doc, ajustes) -> float:
       """V6: refinar una región de 500x500 pintada sobre el borde del sujeto."""
       alfa = removedor.run(doc, replace(ajustes, matting=False, limpieza_color=False)).alpha.copy()
       banda = make_trimap(alfa, 20) == DESCONOCIDO
       filas, columnas = np.nonzero(banda)
       cy, cx = int(filas[len(filas) // 2]), int(columnas[len(columnas) // 2])
       y0, x0 = max(0, cy - LADO_REGION // 2), max(0, cx - LADO_REGION // 2)
       pintado = np.zeros_like(banda)
       pintado[y0 : y0 + LADO_REGION, x0 : x0 + LADO_REGION] = banda[y0 : y0 + LADO_REGION, x0 : x0 + LADO_REGION]
       caja = region_bbox(pintado)
       matter = ClassicMatter()
       refine_region(doc.rgb, alfa.copy(), pintado, matter, caja)  # calentamiento
       inicio = perf_counter()
       refine_region(doc.rgb, alfa, pintado, matter, caja)
       return perf_counter() - inicio
   ```
3. Después de `parser.add_argument("--repeticiones", type=int, default=3)` agregar:
   ```python
       parser.add_argument("--refinar", action="store_true", help="Medir V6 (refinar 500x500)")
   ```
4. Reemplazar la línea `    removedor.run(doc, ajustes)  # calentamiento: sesión ONNX y compilación de numba`
   por:
   ```python
       removedor.run(doc, ajustes)  # calentamiento: sesión ONNX y compilación de numba
       if args.refinar:
           segundos = medir_refinado(removedor, doc, ajustes)
           estado = "OK" if segundos <= LIMITE_REFINAR_S else "FUERA DE LIMITE"
           print(f"refinar {LADO_REGION}x{LADO_REGION}: {segundos:.2f}s, limite {LIMITE_REFINAR_S:.0f}s: {estado}")
           return 0 if segundos <= LIMITE_REFINAR_S else 1
   ```

**Paso 2 - Ejecutar** con la GPU sin otras cargas (cerrar juegos):
```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\benchmark.py D:\Johan\pruebas\entrada\persona.jpg --refinar
.\.venv\Scripts\python.exe -X utf8 scripts\benchmark.py D:\Johan\pruebas\entrada\persona.jpg
```
Esperado: `refinar 500x500` en menos de 2 s (medición previa: 0.34 s) y V4 sigue en `OK`.

**Commit:**
```powershell
git add scripts/benchmark.py
git commit -m "perf(pipeline): medir refinar borde en una region de 500x500"
```

### Tarea 15: cierre del hito

Sin archivos nuevos.

**Paso 1 - Suite completa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```
Esperado: todo `passed`; `skipped` solo en `tests/golden` sin golden set. Revisar el código de
salida (`$LASTEXITCODE` igual a 0) antes de seguir.

**Paso 2 - Prueba manual** con `.\.venv\Scripts\python.exe -X utf8 -m image_studio`:

1. Abrir una foto de producto con Ctrl+O, otra arrastrándola y otra pegándola desde el navegador.
2. Quitar fondo con preset producto y luego persona; la ventana responde mientras corre.
3. Zoom con la rueda hasta 400% y desplazar con el botón central; el tablero no se deforma.
4. Borrar y conservar con dureza 0% y 100%; deshacer y rehacer 10 veces.
5. Refinar borde sobre pelo; la zona pintada se ve en magenta y desaparece al terminar.
6. B alterna original y recorte.
7. Guardar PNG y abrirlo en otro programa sobre fondo de color: sin halo del fondo original.
8. Abrir una imagen de 6000x4000: pintar sigue fluido.

Anotar en el PR qué puntos pasaron y cualquier problema.

**Paso 3 - PR a develop:**
```powershell
git push -u origin feature/hito-2-editor
gh pr create --base develop --title "feat(ui): editor de recorte con pinceles e historial (hito 2)"
```
El cuerpo incluye qué cambia, por qué, archivos, resultado de la suite, V6 y V8, resultado de
la prueba manual y dependencias nuevas (PySide6-Essentials, pytest-qt). Integración por squash.

---

## Cobertura de la spec en este hito

| Requisito | Tarea |
|---|---|
| Abrir imagen: diálogo, arrastrar y soltar, pegar | 7, 11 |
| Quitar fondo en segundo plano con presets | 8, 11 |
| Lienzo con zoom, desplazamiento, tablero y antes/después | 9, 10, 11 |
| Pinceles Conservar y Borrar con tamaño y dureza | 4, 6, 11 |
| Refinar borde re-ejecutando el matting solo en la región | 5, 6, 11 |
| Historial por tiles, 50 pasos o 1 GB | 3, 6 |
| Guardar PNG transparente | 6, 11 |
| Imagen mayor a 8000 px | Decidido sin pirámide (medición), prueba manual 8 |
| Modelo no descargado: la app abre igual | 11 (el modelo se carga al primer quitar fondo) |
| V6 | 5, 14 |
| V8 | 6 |
| V10 (fronteras sin Qt) | 6 (paso 5) |
| Interfaz `Tool`, panel de lotes, presets propios, diálogo de exportación, ViTMatte | Hito 3 |
