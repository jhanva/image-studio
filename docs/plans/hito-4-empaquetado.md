# Plan de implementación - Hito 4: instalador que se adapta al equipo

Spec: [../spec.md](../spec.md). Flujo: [../repo-workflow.md](../repo-workflow.md).
Hitos anteriores: [hito-1-motor.md](hito-1-motor.md), [hito-2-editor.md](hito-2-editor.md),
[hito-3-suite.md](hito-3-suite.md).
Rama: `feature/hito-4-empaquetado` desde `develop`. Un commit por tarea; PR a `develop` (squash);
versión 0.4.0 por rama `agent/`; `develop` a `main` con merge commit y etiqueta.

## Objetivo del hito

Un solo instalador para Windows 10/11 de 64 bits que funcione en PCs distintos, incluidos los
menos potentes:

- La app detecta el equipo (GPU NVIDIA y su memoria, RAM, núcleos) y elige modelo y
  dispositivo; si la GPU falla, sigue en CPU y lo avisa.
- Nuevo modelo intermedio **BiRefNet liviano** (autorizado por el usuario el 2026-10-23).
- Instalador por usuario (sin permisos de administrador) con accesos directos, desinstalador y
  preparación del motor durante la instalación.

## Mediciones que fundamentan el diseño (2026-10-23)

Imagen de 4000x3000, solo inferencia del modelo, RTX 3050 8 GB con la GPU libre, i5-10400:

| Modelo | CUDA | VRAM extra | DirectML | CPU 6 hilos |
|---|---|---|---|---|
| BiRefNet | 1.56 s | 7242 MB | no corre: cae a CPU sin avisar (27 s) | 33 s |
| BiRefNet liviano | 0.77 s | 6216 MB | sin memoria de video | 13 s |
| ISNet | 0.13 s | 1098 MB | 0.12 s | 1.5 s |

- Pico de RAM del proceso: 1.8 GB.
- **DirectML se descarta**: no corre BiRefNet y solo acelera ISNet, que en CPU ya tarda menos de 2 s.
- BiRefNet liviano: MD5 `4fab47adc4ff364be1713e97b7e66334` (coincide con rembg),
  SHA-256 `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`, 224005088 bytes.
  En una imagen sintética difiere de BiRefNet en el borde 0.11 de media (ISNet 0.14); con fotos
  reales se mide con el golden set.

Prueba exploratoria con PyInstaller 6.22.3 (carpeta, sin instalador):

| Hallazgo | Consecuencia en el plan |
|---|---|
| CUDA funciona en el ejecutable si se copian `nvidia/cu13/bin/x86_64/*.dll` y `nvidia/cudnn/bin/*.dll` y se cargan con `onnxruntime.preload_dlls(directory=...)` | Tarea 9 |
| `pymatting` y `image_studio` leen su versión con `importlib.metadata`; sin `copy_metadata` el ejecutable falla | Tarea 10 |
| El proveedor TensorRT depende de DLL que no existen | Se excluye del paquete |
| Las DLL de Visual C++ (`msvcp140`, `vcruntime140`, `vcruntime140_1`) quedan dentro del paquete | No hace falta instalar el redistribuible |
| **Primera ejecución: importar pymatting tarda 42 s** (numba compila); con caché, 0.8 s. La caché queda en `%LOCALAPPDATA%\numba\Cache` | Tareas 7 y 11: carga diferida, preparación en segundo plano y durante la instalación |
| Tamaño de la carpeta: 2.3 GB (1.6 GB son CUDA y cuDNN) | Modelos fuera del instalador; se descargan al primer uso |

## Mapa de archivos

- Modificar: `docs/spec.md`, `README.md`, `requirements-dev.txt`,
  `src/image_studio/engines/model_manager.py`, `engines/segment_birefnet.py`,
  `engines/onnx_segmenter.py`, `engines/matting_classic.py`, `engines/decontaminate.py`,
  `pipeline/settings.py`, `pipeline/factory.py`, `pipeline/remove_bg.py`,
  `pipeline/remover_cache.py`, `cli.py`, `__main__.py`, `ui/main_window.py`, `ui/app.py`,
  `tools/background_removal/editor.py`, `tools/batch/panel.py`, `scripts/benchmark.py`
- Crear: `src/image_studio/engines/hardware.py`, `src/image_studio/engines/warmup.py`,
  `src/image_studio/pipeline/device_choice.py`, `packaging/lanzador.py`,
  `packaging/image_studio.spec`, `packaging/instalador.iss`, `scripts/build.ps1`
- Tests nuevos: `tests/engines/test_hardware.py`, `tests/engines/test_warmup.py`,
  `tests/pipeline/test_device_choice.py`
- Tests modificados: `tests/engines/test_model_manager.py`, `tests/engines/test_segmenters_real.py`,
  `tests/pipeline/test_remover_cache.py`, `tests/test_cli.py`, `tests/test_main.py`,
  `tests/ui/test_main_window.py`, `tests/tools/test_editor.py`

Rutas `engines/...`, `pipeline/...`, `ui/...` y `tools/...` relativas a `src/image_studio/`.
Comandos desde la raíz del repo en PowerShell; cada commit solo con el test en verde.

---

## Fase A - Spec y modelo intermedio

### Tarea 1: actualizar la spec

**Archivos:** modificar `docs/spec.md`

Sin test (documental). Cambios exactos:

1. Tabla 3.1, fila Inferencia: agregar al final de la columna Elección, antes del `|` final,
   el texto ` Un solo instalador con CUDA; DirectML descartado tras medirlo (no corre BiRefNet).`
2. Tabla 3.2: agregar después de la fila de Segmentación calidad la fila
   `| Segmentación intermedia | BiRefNet liviano (Swin tiny), ONNX, entrada 1024x1024 | MIT | PCs sin GPU NVIDIA de 8 GB: unos 13 s en CPU |`.
3. Sección 3.7: agregar al final las líneas
   `- Requisitos mínimos: Windows 10/11 de 64 bits, 8 GB de RAM, 4 GB libres en disco (2.3 GB la app y 1.3 GB los modelos). GPU NVIDIA de 8 GB opcional.`
   y
   `- Selección automática: con GPU NVIDIA de 8 GB o más, BiRefNet en GPU; en otro caso BiRefNet liviano en CPU. Si la GPU falla, se repite en CPU y se avisa.`
4. Sección 4, lista "Excluido del MVP": reemplazar `- Instalador `.exe`, auto-actualización, sistema de licencias.`
   por `- Auto-actualización y sistema de licencias (el instalador llega en el Hito 4).`
   y reemplazar `- Soporte DirectML para GPU AMD/Intel (el equipo objetivo es NVIDIA).`
   por `- Aceleración en GPU AMD/Intel: DirectML no corre BiRefNet (medido en el Hito 4); esos equipos usan CPU.`

**Verificar:**
```powershell
Select-String -Path docs\spec.md -Pattern "DirectML descartado","BiRefNet liviano","Requisitos mínimos","Selección automática","llega en el Hito 4","no corre BiRefNet \(medido"
```
Esperado: 6 coincidencias.

**Commit:**
```powershell
git add docs/spec.md
git commit -m "docs(spec): definir instalador unico y seleccion automatica del hito 4"
```

### Tarea 2: registrar BiRefNet liviano

**Archivos:** modificar `src/image_studio/engines/model_manager.py`,
`src/image_studio/engines/segment_birefnet.py`, `src/image_studio/pipeline/factory.py`,
`src/image_studio/pipeline/settings.py`, `tests/engines/test_model_manager.py`,
`tests/engines/test_segmenters_real.py`

Son dos archivos de producción con lógica (`model_manager`, `segment_birefnet`) y dos registros
de una línea (`factory`, `settings`).

**Paso 1 - Tests que fallan.**

En `tests/engines/test_model_manager.py`, reemplazar
`    assert set(MODELOS) == {"birefnet", "isnet"}` por
`    assert set(MODELOS) == {"birefnet", "birefnet_lite", "isnet"}`.

En `tests/engines/test_segmenters_real.py`, reemplazar
`from image_studio.engines.segment_birefnet import BiRefNetSegmenter` por
`from image_studio.engines.segment_birefnet import BiRefNetLiteSegmenter, BiRefNetSegmenter`
y `CLASES = {"birefnet": BiRefNetSegmenter, "isnet": ISNetSegmenter}` por
`CLASES = {"birefnet": BiRefNetSegmenter, "birefnet_lite": BiRefNetLiteSegmenter, "isnet": ISNetSegmenter}`.

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_model_manager.py tests/engines/test_segmenters_real.py -q
```
Esperado: `ImportError: cannot import name 'BiRefNetLiteSegmenter'`.

**Paso 3 - Implementar.**

En `model_manager.py`, dentro de `MODELOS`, después de la entrada `"birefnet"` agregar:
```python
    "birefnet_lite": ModelSpec(
        "birefnet_lite",
        "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
        _BASE_URL + "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
        "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333",
        224005088,
    ),
```

Al final de `segment_birefnet.py` agregar:
```python


class BiRefNetLiteSegmenter(BiRefNetSegmenter):
    """BiRefNet con backbone Swin tiny: la mitad de tiempo y 6 veces menos peso en disco."""

    nombre = "birefnet_lite"
```

En `factory.py`, reemplazar
`from image_studio.engines.segment_birefnet import BiRefNetSegmenter` por
`from image_studio.engines.segment_birefnet import BiRefNetLiteSegmenter, BiRefNetSegmenter`
y `_SEGMENTADORES = {"birefnet": BiRefNetSegmenter, "isnet": ISNetSegmenter}` por
`_SEGMENTADORES = {"birefnet": BiRefNetSegmenter, "birefnet_lite": BiRefNetLiteSegmenter, "isnet": ISNetSegmenter}`.

En `settings.py`, reemplazar `MODELOS_SEGMENTACION = ("birefnet", "isnet")` por
`MODELOS_SEGMENTACION = ("birefnet", "birefnet_lite", "isnet")`.

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines tests/pipeline -q
```
Esperado: todo `passed` (el modelo liviano ya está en `%LOCALAPPDATA%\ImageStudio\models`).

**Commit:**
```powershell
git add src/image_studio/engines/model_manager.py src/image_studio/engines/segment_birefnet.py src/image_studio/pipeline/factory.py src/image_studio/pipeline/settings.py tests/engines/test_model_manager.py tests/engines/test_segmenters_real.py
git commit -m "feat(engines): agregar birefnet liviano como modelo intermedio"
```

---

## Fase B - Adaptarse al equipo

### Tarea 3: detección del equipo

**Archivos:** crear `src/image_studio/engines/hardware.py`, `tests/engines/test_hardware.py`

**Paso 1 - Tests que fallan:**
```python
from image_studio.engines.hardware import Hardware, detect_hardware, parse_nvidia_smi


def test_lee_la_primera_gpu():
    assert parse_nvidia_smi("NVIDIA GeForce RTX 3050, 8192\n") == ("NVIDIA GeForce RTX 3050", 8192)
    assert parse_nvidia_smi("Quadro P1000, rev 2, 4096\nOtra, 2048\n") == ("Quadro P1000, rev 2", 4096)


def test_sin_nvidia():
    assert parse_nvidia_smi("") == (None, 0)
    assert parse_nvidia_smi("error inesperado") == (None, 0)


def test_detecta_con_consulta_inyectada():
    equipo = detect_hardware(consultar=lambda: "NVIDIA GeForce RTX 3050, 8192")
    assert equipo.gpu == "NVIDIA GeForce RTX 3050" and equipo.vram_mb == 8192
    assert equipo.tiene_nvidia and equipo.ram_mb > 0 and equipo.cpus >= 1


def test_descripciones():
    assert Hardware("RTX 3050", 8192, 16384, 6).describir() == "RTX 3050 (8 GB), 16 GB de RAM"
    assert Hardware(None, 0, 8192, 4).describir() == "Sin GPU NVIDIA, 8 GB de RAM, 4 núcleos"
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_hardware.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.engines.hardware'`.

**Paso 3 - Implementar** `src/image_studio/engines/hardware.py`:
```python
"""Detección del equipo: GPU NVIDIA y su memoria, RAM y núcleos."""

from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Hardware:
    gpu: str | None
    vram_mb: int
    ram_mb: int
    cpus: int

    @property
    def tiene_nvidia(self) -> bool:
        return self.gpu is not None and self.vram_mb > 0

    def describir(self) -> str:
        ram = f"{self.ram_mb / 1024:.0f} GB de RAM"
        if self.tiene_nvidia:
            return f"{self.gpu} ({self.vram_mb / 1024:.0f} GB), {ram}"
        return f"Sin GPU NVIDIA, {ram}, {self.cpus} núcleos"


def parse_nvidia_smi(salida: str) -> tuple[str | None, int]:
    """Primera GPU de las líneas 'nombre, memoria_mb'; (None, 0) si no hay ninguna válida."""
    for linea in salida.strip().splitlines():
        partes = [p.strip() for p in linea.rsplit(",", 1)]
        if len(partes) == 2 and partes[1].isdigit():
            return partes[0], int(partes[1])
    return None, 0


def _consultar_nvidia_smi() -> str:
    # nvidia-smi viene con el driver; si no está, el equipo no tiene GPU NVIDIA utilizable.
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return resultado.stdout if resultado.returncode == 0 else ""


class _EstadoMemoria(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _ram_mb() -> int:
    estado = _EstadoMemoria()
    estado.dwLength = ctypes.sizeof(estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        return 0
    return int(estado.ullTotalPhys // 2**20)


def detect_hardware(consultar=_consultar_nvidia_smi) -> Hardware:
    gpu, vram = parse_nvidia_smi(consultar())
    return Hardware(gpu, vram, _ram_mb(), os.cpu_count() or 1)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/engines/hardware.py tests/engines/test_hardware.py
git commit -m "feat(engines): detectar gpu nvidia, memoria y nucleos del equipo"
```

### Tarea 4: elegir modelo y dispositivo

**Archivos:** crear `src/image_studio/pipeline/device_choice.py`,
`tests/pipeline/test_device_choice.py`

**Paso 1 - Tests que fallan:**
```python
import pytest

from image_studio.engines.hardware import Hardware
from image_studio.pipeline.device_choice import choose

RTX_8GB = Hardware("NVIDIA GeForce RTX 3050", 8192, 16384, 6)
GTX_4GB = Hardware("NVIDIA GeForce GTX 1650", 4096, 8192, 4)
SIN_GPU = Hardware(None, 0, 8192, 4)


def test_automatico_con_gpu_grande():
    eleccion = choose("auto", RTX_8GB)
    assert (eleccion.modelo, eleccion.dispositivo) == ("birefnet", "auto")
    assert "GPU" in eleccion.descripcion


def test_automatico_sin_gpu_usa_el_liviano_en_cpu():
    eleccion = choose("auto", SIN_GPU)
    assert (eleccion.modelo, eleccion.dispositivo) == ("birefnet_lite", "cpu")
    assert "sin GPU NVIDIA" in eleccion.descripcion


def test_gpu_pequena_va_a_cpu_salvo_isnet():
    assert choose("birefnet", GTX_4GB).dispositivo == "cpu"
    assert choose("isnet", GTX_4GB).dispositivo == "auto"
    assert "4096 MB" in choose("birefnet_lite", GTX_4GB).descripcion


def test_gpu_marcada_como_fallida_va_a_cpu():
    assert choose("birefnet", RTX_8GB, gpu_fallida={"birefnet"}).dispositivo == "cpu"


def test_modelo_desconocido():
    with pytest.raises(ValueError):
        choose("u2net", RTX_8GB)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_device_choice.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.device_choice'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/device_choice.py`:
```python
"""Elegir modelo y dispositivo según el equipo."""

from __future__ import annotations

from dataclasses import dataclass

from image_studio.engines.hardware import Hardware

# VRAM adicional medida el 2026-10-23 en una RTX 3050 con enable_mem_pattern=False
# (7242, 6216 y 1098 MB), redondeada hacia arriba.
VRAM_NECESARIA_MB = {"birefnet": 7500, "birefnet_lite": 6500, "isnet": 1500}


@dataclass(frozen=True)
class Eleccion:
    modelo: str
    dispositivo: str
    """"auto" usa CUDA si está disponible; "cpu" fuerza CPU."""
    descripcion: str


def choose(modelo: str, equipo: Hardware, gpu_fallida: frozenset[str] | set[str] = frozenset()) -> Eleccion:
    if modelo == "auto":
        modelo = "birefnet" if equipo.vram_mb >= VRAM_NECESARIA_MB["birefnet"] else "birefnet_lite"
    if modelo not in VRAM_NECESARIA_MB:
        raise ValueError(f"Modelo no soportado: {modelo}")
    necesaria = VRAM_NECESARIA_MB[modelo]
    if equipo.tiene_nvidia and equipo.vram_mb >= necesaria and modelo not in gpu_fallida:
        return Eleccion(modelo, "auto", f"{modelo} en GPU ({equipo.gpu})")
    if not equipo.tiene_nvidia:
        motivo = "sin GPU NVIDIA"
    elif modelo in gpu_fallida:
        motivo = "la GPU falló antes"
    else:
        motivo = f"la GPU tiene {equipo.vram_mb} MB y el modelo necesita {necesaria} MB"
    return Eleccion(modelo, "cpu", f"{modelo} en CPU ({motivo})")
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `5 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/device_choice.py tests/pipeline/test_device_choice.py
git commit -m "feat(pipeline): elegir modelo y dispositivo segun el equipo"
```

### Tarea 5: modelo automático y respaldo a CPU en el caché

**Archivos:** modificar `src/image_studio/pipeline/settings.py`,
`src/image_studio/pipeline/remove_bg.py`, `src/image_studio/pipeline/remover_cache.py`,
`tests/pipeline/test_remover_cache.py`, `tests/tools/test_editor.py`

`settings` y `remove_bg` solo cambian una constante y un campo; la lógica nueva está en
`remover_cache`.

**Paso 1 - Tests que fallan.** En `tests/pipeline/test_remover_cache.py`, agregar a los imports
del inicio:
```python
from pathlib import Path

import numpy as np

from image_studio.core.image_io import ImageDoc
from image_studio.engines.hardware import Hardware
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.settings import PipelineSettings
```
y al final del archivo:
```python


RTX_8GB = Hardware("RTX", 8192, 16384, 6)
SIN_GPU = Hardware(None, 0, 8192, 4)


class Removedor:
    def __init__(self, modelo, dispositivo, fallar=False):
        self.modelo, self.dispositivo, self.fallar = modelo, dispositivo, fallar

    def run(self, doc, ajustes, usar_alfa_existente=False):
        if self.fallar:
            raise RuntimeError("CUDA out of memory")
        alfa = np.ones(doc.rgb.shape[:2], np.float32)
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.0})


def _doc():
    return ImageDoc(Path("x.png"), np.zeros((8, 8, 3), np.uint8), None, None, None)


def test_automatico_usa_la_eleccion_del_equipo():
    creados = []
    cache = RemoverCache(lambda m, d, p: creados.append((m, d)) or Removedor(m, d), hardware=SIN_GPU)
    resultado = cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet_lite", "cpu")]
    assert "birefnet_lite en CPU" in resultado.dispositivo


def test_si_la_gpu_falla_repite_en_cpu_y_lo_recuerda():
    creados = []

    def crear(modelo, dispositivo, progreso):
        creados.append((modelo, dispositivo))
        return Removedor(modelo, dispositivo, fallar=dispositivo == "auto")

    cache = RemoverCache(crear, hardware=RTX_8GB)
    resultado = cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet", "auto"), ("birefnet", "cpu")]
    assert "la GPU falló" in resultado.dispositivo
    cache.run(_doc(), PipelineSettings())
    assert creados == [("birefnet", "auto"), ("birefnet", "cpu")]


def test_detecta_el_equipo_una_sola_vez():
    cache = RemoverCache(lambda m, d, p: Removedor(m, d))
    assert cache.hardware is cache.hardware
```

En `tests/tools/test_editor.py`, dentro de `test_usa_presets_propios`, reemplazar
`    assert removedor.ajustes[-1] == PipelineSettings(matting=False, banda_px=4)` por:
```python
    usados = removedor.ajustes[-1]
    assert (usados.matting, usados.banda_px) == (False, 4)
    assert usados.modelo in ("birefnet", "birefnet_lite")
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_remover_cache.py -q
```
Esperado: `TypeError: RemoverCache.__init__() got an unexpected keyword argument 'hardware'`.

**Paso 3 - Implementar.**

En `settings.py`:
- reemplazar `MODELOS_SEGMENTACION = ("birefnet", "birefnet_lite", "isnet")` por
  `MODELOS_SEGMENTACION = ("auto", "birefnet", "birefnet_lite", "isnet")`;
- reemplazar `    modelo: str = "birefnet"` por `    modelo: str = "auto"`.

En `remove_bg.py`, en `RemovalResult`, después de
`    tiempos: dict[str, float] = field(default_factory=dict)` agregar:
```python
    dispositivo: str = ""
    """Modelo y dispositivo que se usaron; lo completa RemoverCache."""
```

Reemplazar `src/image_studio/pipeline/remover_cache.py` por:
```python
"""Un removedor por modelo y dispositivo, compartido por todas las herramientas."""

from __future__ import annotations

import threading
from dataclasses import replace

from image_studio.engines.hardware import Hardware, detect_hardware
from image_studio.pipeline.device_choice import choose
from image_studio.pipeline.factory import build_remover


class RemoverCache:
    def __init__(self, crear=build_remover, hardware: Hardware | None = None):
        self._crear = crear
        self._hardware = hardware
        self._removedores: dict[tuple[str, str], object] = {}
        self._gpu_fallida: set[str] = set()
        # Cargar BiRefNet tarda unos 11 s; el candado evita cargarlo dos veces si el editor y
        # el panel de lotes lo piden a la vez.
        self._candado = threading.Lock()

    @property
    def hardware(self) -> Hardware:
        with self._candado:
            if self._hardware is None:
                self._hardware = detect_hardware()
            return self._hardware

    def get(self, modelo: str, dispositivo: str = "auto", progreso=None):
        clave = (modelo, dispositivo)
        with self._candado:
            if clave not in self._removedores:
                self._removedores[clave] = self._crear(modelo, dispositivo, progreso)
            return self._removedores[clave]

    def run(self, doc, ajustes, usar_alfa_existente: bool = False):
        """Resuelve el modelo automático, corre en GPU si conviene y, si la GPU falla, repite en CPU."""
        eleccion = choose(ajustes.modelo, self.hardware, self._gpu_fallida)
        ajustes = replace(ajustes, modelo=eleccion.modelo)
        if eleccion.dispositivo != "cpu":
            try:
                resultado = self.get(eleccion.modelo, eleccion.dispositivo).run(doc, ajustes, usar_alfa_existente)
                return replace(resultado, dispositivo=eleccion.descripcion)
            except Exception:  # memoria de video insuficiente, driver viejo o DLL de CUDA ausentes
                self._gpu_fallida.add(eleccion.modelo)
                eleccion = choose(eleccion.modelo, self.hardware, self._gpu_fallida)
        resultado = self.get(eleccion.modelo, "cpu").run(doc, ajustes, usar_alfa_existente)
        return replace(resultado, dispositivo=eleccion.descripcion)
```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline tests/tools -q
```
Esperado: todo `passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/settings.py src/image_studio/pipeline/remove_bg.py src/image_studio/pipeline/remover_cache.py tests/pipeline/test_remover_cache.py tests/tools/test_editor.py
git commit -m "feat(pipeline): modelo automatico y respaldo a cpu si la gpu falla"
```

### Tarea 6: usar la elección en editor, lotes, CLI y benchmark

**Archivos:** modificar `src/image_studio/tools/background_removal/editor.py`,
`src/image_studio/tools/batch/panel.py`, `src/image_studio/cli.py`, `scripts/benchmark.py`,
`tests/tools/test_editor.py`, `tests/test_cli.py`

Cambios de una o dos líneas por archivo para que todos pasen por la misma elección.

**Paso 1 - Tests que fallan.**

En `tests/tools/test_editor.py`, dentro de `test_quitar_fondo_en_segundo_plano`, reemplazar
`    assert "Fondo quitado" in abierto.ultimo_mensaje` por:
```python
    assert "Fondo quitado" in abierto.ultimo_mensaje
    assert " en GPU " in abierto.ultimo_mensaje or " en CPU " in abierto.ultimo_mensaje
```

Agregar al final de `tests/test_cli.py`:
```python


def test_resuelve_el_modelo_automatico(tmp_path, escribir_png, removedor_falso):
    from image_studio.engines.hardware import Hardware

    escribir_png(tmp_path / "entrada" / "a.png")
    pedidos = []

    def fabrica(modelo, dispositivo, progreso):
        pedidos.append((modelo, dispositivo))
        return removedor_falso

    codigo = main(
        ["batch", str(tmp_path / "entrada"), str(tmp_path / "salida")],
        crear_removedor=fabrica,
        hardware=Hardware(None, 0, 8192, 4),
    )
    assert codigo == 0
    assert pedidos == [("birefnet_lite", "cpu")]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/tools/test_editor.py tests/test_cli.py -q
```
Esperado: 2 fallos (el mensaje no menciona el dispositivo; `main()` no acepta `hardware`).

**Paso 3 - Implementar.**

En `tools/background_removal/editor.py`:
- en `_ejecutar_removedor`, reemplazar
  `        return self._cache.get(ajustes.modelo).run(doc, ajustes)` por
  `        return self._cache.run(doc, ajustes)`;
- en `_fondo_quitado`, reemplazar
  `        self.informar(f"Fondo quitado en {total:.1f} s.{aviso}")` por
  `        self.informar(f"Fondo quitado en {total:.1f} s con {resultado.dispositivo}.{aviso}")`.

En `tools/batch/panel.py`, en `_correr`, reemplazar
`        removedor = self._cache.get(ajustes.modelo)` por
`        removedor = self._cache  # elige modelo y dispositivo y repite en CPU si la GPU falla`.

En `cli.py`:
- agregar a los imports `from image_studio.engines.hardware import Hardware, detect_hardware` y
  `from image_studio.pipeline.device_choice import choose`;
- reemplazar la firma `def main(argv: list[str] | None = None, crear_removedor=build_remover) -> int:`
  por `def main(argv: list[str] | None = None, crear_removedor=build_remover, hardware: Hardware | None = None) -> int:`;
- reemplazar
  `    removedor = crear_removedor(ajustes.modelo, "cpu" if args.cpu else "auto", _progreso_descarga)` por:
  ```python
      eleccion = choose(ajustes.modelo, hardware or detect_hardware())
      dispositivo = "cpu" if args.cpu else eleccion.dispositivo
      ajustes = replace(ajustes, modelo=eleccion.modelo)
      print(f"Usando {eleccion.descripcion}" + (" (forzado a CPU)" if args.cpu else ""))
      removedor = crear_removedor(ajustes.modelo, dispositivo, _progreso_descarga)
  ```

En `scripts/benchmark.py`:
- agregar a los imports `from image_studio.engines.hardware import detect_hardware` y
  `from image_studio.pipeline.device_choice import choose`;
- reemplazar `    removedor = build_remover(ajustes.modelo, dispositivo)` por:
  ```python
      eleccion = choose(ajustes.modelo, detect_hardware())
      ajustes = replace(ajustes, modelo=eleccion.modelo)
      print(f"Usando {eleccion.descripcion}")
      removedor = build_remover(ajustes.modelo, "cpu" if args.cpu else eleccion.dispositivo)
  ```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```
Esperado: todo `passed`; `skipped` solo en `tests/golden`.

**Commit:**
```powershell
git add src/image_studio/tools/background_removal/editor.py src/image_studio/tools/batch/panel.py src/image_studio/cli.py scripts/benchmark.py tests/tools/test_editor.py tests/test_cli.py
git commit -m "feat(pipeline): usar la eleccion automatica en editor, lotes y cli"
```

### Tarea 7: mostrar el equipo y preparar el motor sin congelar la ventana

**Archivos:** crear `src/image_studio/engines/warmup.py`, `tests/engines/test_warmup.py`;
modificar `src/image_studio/engines/matting_classic.py`, `src/image_studio/engines/decontaminate.py`,
`src/image_studio/ui/main_window.py`, `src/image_studio/ui/app.py`, `tests/ui/test_main_window.py`

Hoy importar pymatting compila con numba al importar el módulo (42 s sin caché). La carga pasa a
ser diferida: los módulos guardan `None` y la primera llamada importa pymatting. Los tests de
Hito 1 que reemplazan `estimate_alpha_cf`, `ichol` o `estimate_foreground_ml` siguen funcionando
porque los atributos existen en el módulo.

**Paso 1 - Tests que fallan.**

`tests/engines/test_warmup.py`:
```python
import subprocess
import sys


def test_importar_los_motores_no_carga_pymatting():
    codigo = (
        "import sys\n"
        "import image_studio.engines.matting_classic, image_studio.engines.decontaminate\n"
        "import image_studio.pipeline.session\n"
        "print('pymatting' in sys.modules)\n"
    )
    salida = subprocess.run([sys.executable, "-X", "utf8", "-c", codigo], capture_output=True, text=True, check=True)
    assert salida.stdout.strip() == "False"


def test_preparar_carga_pymatting():
    from image_studio.engines import decontaminate, matting_classic
    from image_studio.engines.warmup import prepare_engines

    assert prepare_engines() >= 0.0
    assert matting_classic.estimate_alpha_cf is not None
    assert matting_classic.ichol is not None
    assert decontaminate.estimate_foreground_ml is not None
```

Agregar al final de `tests/ui/test_main_window.py`:
```python


def test_muestra_el_equipo_en_la_barra_de_estado(qtbot):
    ventana, _ = _ventana(qtbot)
    ventana.mostrar_equipo("RTX 3050 (8 GB), 16 GB de RAM")
    assert ventana.etiqueta_equipo.text() == "RTX 3050 (8 GB), 16 GB de RAM"
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/engines/test_warmup.py tests/ui/test_main_window.py -q
```
Esperado: `AssertionError` (`True` en lugar de `False`), `ModuleNotFoundError` para
`image_studio.engines.warmup` y `AttributeError` por `mostrar_equipo`.

**Paso 3 - Implementar.**

En `engines/matting_classic.py`:
- reemplazar las dos líneas
  `from pymatting import estimate_alpha_cf` y `from pymatting.preconditioner.ichol import ichol`
  por:
  ```python
  # pymatting compila con numba al importarse (unos 40 s la primera vez en un equipo nuevo);
  # se carga en la primera llamada para no congelar el arranque de la app.
  estimate_alpha_cf = None
  ichol = None


  def _cargar_pymatting() -> None:
      global estimate_alpha_cf, ichol
      if estimate_alpha_cf is None:
          from pymatting import estimate_alpha_cf as funcion

          estimate_alpha_cf = funcion
      if ichol is None:
          from pymatting.preconditioner.ichol import ichol as funcion

          ichol = funcion
  ```
- al inicio de `refine`, antes de `alfa = grueso.astype(np.float32, copy=True)`, agregar
  `        _cargar_pymatting()`.

En `engines/decontaminate.py`:
- reemplazar `from pymatting import estimate_foreground_ml` por:
  ```python
  # Ver matting_classic: pymatting se importa en la primera llamada.
  estimate_foreground_ml = None


  def _cargar_pymatting() -> None:
      global estimate_foreground_ml
      if estimate_foreground_ml is None:
          from pymatting import estimate_foreground_ml as funcion

          estimate_foreground_ml = funcion
  ```
  (la asignación `numba.config.THREADING_LAYER = "threadsafe"` y su comentario quedan donde están,
  después de los imports).
- al inicio de `decontaminate`, antes de `    salida = rgb.copy()`, agregar `    _cargar_pymatting()`.

`src/image_studio/engines/warmup.py`:
```python
"""Preparar el motor: importar pymatting para que numba compile (o lea su caché)."""

from __future__ import annotations

from time import perf_counter


def prepare_engines() -> float:
    """Devuelve los segundos que tardó; unos 40 s la primera vez en un equipo nuevo y menos de 1 s después."""
    from image_studio.engines import decontaminate, matting_classic

    inicio = perf_counter()
    matting_classic._cargar_pymatting()
    decontaminate._cargar_pymatting()
    return perf_counter() - inicio
```

En `ui/main_window.py`:
- agregar `QLabel` a los imports de `PySide6.QtWidgets`;
- al final de `__init__`, después de `self.lista.setCurrentRow(0)`, agregar:
  ```python
          self.etiqueta_equipo = QLabel("")
          self.statusBar().addPermanentWidget(self.etiqueta_equipo)
  ```
- agregar el método:
  ```python
      def mostrar_equipo(self, texto: str) -> None:
          self.etiqueta_equipo.setText(texto)
  ```

En `ui/app.py`:
- agregar a los imports `from image_studio.engines.warmup import prepare_engines`,
  `from image_studio.pipeline.device_choice import choose` y
  `from image_studio.workers.tasks import ejecutar`;
- en `crear_herramientas`, reemplazar la firma y las dos primeras líneas para recibir y devolver
  el caché:
  ```python
  def crear_herramientas(cache: RemoverCache, presets: PresetStore | None = None) -> list[Tool]:
      presets = presets or PresetStore()
  ```
- en `crear_ventana`, reemplazar `    herramientas = crear_herramientas()` por:
  ```python
      cache = RemoverCache()
      herramientas = crear_herramientas(cache)
  ```
  y, antes de `    if rutas:`, agregar:
  ```python
      eleccion = choose("auto", cache.hardware)
      ventana.mostrar_equipo(f"{cache.hardware.describir()} | automático: {eleccion.descripcion}")
      ventana.statusBar().showMessage("Preparando el motor (la primera vez puede tardar un minuto)...")
      ejecutar(
          prepare_engines,
          al_terminar=lambda segundos: ventana.statusBar().showMessage(f"Motor listo ({segundos:.0f} s)"),
          al_fallar=lambda mensaje: ventana.statusBar().showMessage(f"Error al preparar el motor: {mensaje}"),
      )
  ```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```
Esperado: todo `passed`.

**Commit:**
```powershell
git add src/image_studio/engines/warmup.py src/image_studio/engines/matting_classic.py src/image_studio/engines/decontaminate.py src/image_studio/ui/main_window.py src/image_studio/ui/app.py tests/engines/test_warmup.py tests/ui/test_main_window.py
git commit -m "perf(ui): preparar el motor en segundo plano y mostrar el equipo"
```

### Tarea 8: comandos `preparar` y `diagnostico`

**Archivos:** modificar `src/image_studio/cli.py`, `src/image_studio/__main__.py`,
`tests/test_cli.py`, `tests/test_main.py`

**Paso 1 - Tests que fallan.** Agregar al final de `tests/test_cli.py`:
```python


def test_preparar(capsys):
    assert main(["preparar"]) == 0
    assert "Motor listo" in capsys.readouterr().out


def test_diagnostico_sin_modelos(tmp_path, monkeypatch, capsys):
    from image_studio.engines.hardware import Hardware

    monkeypatch.setenv("IMAGE_STUDIO_MODELS_DIR", str(tmp_path / "vacio"))
    assert main(["diagnostico"], hardware=Hardware(None, 0, 8192, 4)) == 0
    salida = capsys.readouterr().out
    assert "Sin GPU NVIDIA" in salida
    assert "birefnet_lite en CPU" in salida
    assert "no descargado" in salida
```

Agregar al final de `tests/test_main.py`:
```python


def test_preparar_y_diagnostico_van_a_la_cli(monkeypatch):
    import image_studio.__main__ as modulo

    llamadas = []
    monkeypatch.setattr(modulo, "cli_main", lambda argv: llamadas.append(argv) or 0)
    assert principal(["preparar"]) == 0
    assert principal(["diagnostico"]) == 0
    assert llamadas == [["preparar"], ["diagnostico"]]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_cli.py tests/test_main.py -q
```
Esperado: `SystemExit: 2` por `invalid choice: 'preparar'` y la llamada a la UI en lugar de la CLI.

**Paso 3 - Implementar.**

En `__main__.py`, reemplazar `    if argv and argv[0] in ("batch", "-h", "--help"):` por
`    if argv and argv[0] in ("batch", "preparar", "diagnostico", "-h", "--help"):`.

En `cli.py`:
- agregar a los imports:
  ```python
  import platform
  from time import perf_counter

  import numpy as np

  from image_studio import __version__
  from image_studio.core.image_io import ImageDoc
  from image_studio.engines.model_manager import MODELOS, available_providers, models_dir
  from image_studio.engines.warmup import prepare_engines
  ```
- en `build_parser`, después de crear el subcomando `batch` y sus argumentos (antes de
  `    return parser`), agregar:
  ```python
      comandos.add_parser("preparar", help="Compilar el motor de matting (lo usa el instalador)")
      comandos.add_parser("diagnostico", help="Mostrar el equipo, la elección automática y probar el motor")
  ```
- al inicio de `main`, después de `    args = build_parser().parse_args(argv)`, agregar:
  ```python
      if args.comando == "preparar":
          print(f"Motor listo en {prepare_engines():.1f} s")
          return 0
      if args.comando == "diagnostico":
          return _diagnostico(hardware or detect_hardware(), crear_removedor)
  ```
- agregar la función al final del archivo:
  ```python


  def _diagnostico(equipo: Hardware, crear_removedor) -> int:
      print(f"Image Studio {__version__} en Python {platform.python_version()}")
      print(f"Ejecutable: {'sí' if getattr(sys, 'frozen', False) else 'no'}")
      print(f"Equipo: {equipo.describir()}")
      print(f"Proveedores ONNX: {', '.join(available_providers())}")
      eleccion = choose("auto", equipo)
      print(f"Automático: {eleccion.descripcion}")
      print(f"Motor de matting listo en {prepare_engines():.1f} s")
      if not (models_dir() / MODELOS[eleccion.modelo].archivo).exists():
          print(f"Modelo {eleccion.modelo} no descargado: se descargará al primer uso")
          return 0
      removedor = crear_removedor(eleccion.modelo, eleccion.dispositivo, None)
      filas, columnas = np.mgrid[:600, :800]
      rgb = np.full((600, 800, 3), 235, np.uint8)
      rgb[np.hypot(filas - 300, columnas - 400) <= 180] = (200, 40, 30)
      ajustes = replace(PRESETS["persona"], modelo=eleccion.modelo)
      inicio = perf_counter()
      resultado = removedor.run(ImageDoc(Path("diagnostico.png"), rgb, None, None, None), ajustes)
      print(f"Prueba de recorte: {perf_counter() - inicio:.1f} s, alfa medio {resultado.alpha.mean():.3f}")
      return 0
  ```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_cli.py tests/test_main.py -q
.\.venv\Scripts\python.exe -X utf8 -m image_studio diagnostico
```
Esperado: `passed`, y en el diagnóstico la RTX 3050, `birefnet en GPU` y una prueba de recorte
con alfa medio cercano a 0.3.

**Commit:**
```powershell
git add src/image_studio/cli.py src/image_studio/__main__.py tests/test_cli.py tests/test_main.py
git commit -m "feat(cli): agregar comandos preparar y diagnostico"
```

---

## Fase C - Empaquetado

### Tarea 9: lanzador del ejecutable

**Archivos:** crear `packaging/lanzador.py`; modificar `requirements-dev.txt`

Sin test unitario: se verifica dentro del ejecutable en la tarea 10.

**Paso 1 - Implementar.** Agregar al final de `requirements-dev.txt`:
```text
pyinstaller==6.22.3
```

`packaging/lanzador.py`:
```python
"""Punto de entrada de ImageStudio.exe e image-studio-cli.exe (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _preparar_cuda(base: Path) -> None:
    # En el ejecutable no existe site-packages: las DLL de CUDA y cuDNN se copian a _internal
    # y se cargan desde ahí antes de crear sesiones de ONNX Runtime.
    import onnxruntime

    cuda = base / "nvidia" / "cu13" / "bin" / "x86_64"
    cudnn = base / "nvidia" / "cudnn" / "bin"
    if cuda.is_dir():
        onnxruntime.preload_dlls(cuda=True, cudnn=False, directory=str(cuda))
    if cudnn.is_dir():
        onnxruntime.preload_dlls(cuda=False, cudnn=True, msvc=False, directory=str(cudnn))


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        _preparar_cuda(Path(sys._MEIPASS))
    from image_studio.__main__ import principal

    sys.exit(principal(sys.argv[1:]))
```

```powershell
.\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt
.\.venv\Scripts\python.exe -X utf8 packaging\lanzador.py diagnostico
```
Esperado: el mismo diagnóstico de la tarea 8 (fuera del ejecutable no se precargan DLL).

**Commit:**
```powershell
git add packaging/lanzador.py requirements-dev.txt
git commit -m "build(repo): agregar lanzador para el ejecutable"
```

### Tarea 10: configuración de PyInstaller

**Archivos:** crear `packaging/image_studio.spec`

**Paso 1 - Implementar** `packaging/image_studio.spec`:
```python
# Construye dist\ImageStudio con dos ejecutables que comparten las mismas bibliotecas:
#   ImageStudio.exe        interfaz, sin consola
#   image-studio-cli.exe   batch, preparar y diagnostico, con consola
# Uso: .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist --workpath build packaging\image_studio.spec
import sysconfig
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

RAIZ = Path(SPECPATH).parent
SITE = Path(sysconfig.get_paths()["purelib"])
DLLS_NVIDIA = [(str(p), str(p.parent.relative_to(SITE))) for p in (SITE / "nvidia").rglob("*.dll")]

a = Analysis(
    [str(RAIZ / "packaging" / "lanzador.py")],
    pathex=[str(RAIZ / "src")],
    binaries=DLLS_NVIDIA,
    datas=copy_metadata("pymatting") + copy_metadata("image-studio"),
    hiddenimports=["image_studio.ui.app"],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyInstaller"],
    # numba guarda su caché junto a la fuente; pymatting necesita los .py en disco.
    module_collection_mode={"pymatting": "pyz+py"},
)
# El proveedor TensorRT depende de DLL que no se distribuyen.
a.binaries = [b for b in a.binaries if "tensorrt" not in b[0].lower()]
pyz = PYZ(a.pure)
interfaz = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ImageStudio", console=False)
consola = EXE(pyz, a.scripts, [], exclude_binaries=True, name="image-studio-cli", console=True)
COLLECT(interfaz, consola, a.binaries, a.datas, name="ImageStudio")
```

**Paso 2 - Construir y verificar:**
```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --log-level WARN --distpath dist --workpath build packaging\image_studio.spec
dist\ImageStudio\image-studio-cli.exe diagnostico
```
Esperado: `Ejecutable: sí`, la RTX 3050, `birefnet en GPU` y la prueba de recorte. Tamaño de
`dist\ImageStudio` cercano a 2.3 GB. Abrir `dist\ImageStudio\ImageStudio.exe` a mano: la ventana
aparece sin consola y la barra de estado muestra el equipo.

**Commit:**
```powershell
git add packaging/image_studio.spec
git commit -m "build(repo): configurar pyinstaller con interfaz y consola"
```

### Tarea 11: instalador y script de construcción

**Archivos:** crear `packaging/instalador.iss`, `scripts/build.ps1`

**Paso 1 - Instalar Inno Setup 6** (herramienta de construcción, fuera del `.venv`; puede pedir
permisos de Windows):
```powershell
winget install --id JRSoftware.InnoSetup -e --version 6.7.3 --accept-package-agreements --accept-source-agreements
```

**Paso 2 - Implementar** `packaging/instalador.iss`:
```ini
; Instalador por usuario de Image Studio (Inno Setup 6). Lo invoca scripts\build.ps1 con /DVersion=X.Y.Z.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{80C60E47-96C4-42A4-872C-01027E0D87A6}
AppName=Image Studio
AppVersion={#Version}
AppPublisher=jhanva
DefaultDirName={localappdata}\Programs\Image Studio
DefaultGroupName=Image Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\instalador
OutputBaseFilename=ImageStudio-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ImageStudio.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "..\dist\ImageStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Image Studio"; Filename: "{app}\ImageStudio.exe"
Name: "{autodesktop}\Image Studio"; Filename: "{app}\ImageStudio.exe"; Tasks: escritorio

[Run]
; numba compila el motor la primera vez (unos 40 s); hacerlo aquí evita esperar al abrir la app.
Filename: "{app}\image-studio-cli.exe"; Parameters: "preparar"; StatusMsg: "Preparando el motor de recorte (puede tardar un minuto)..."; Flags: runhidden waituntilterminated
Filename: "{app}\ImageStudio.exe"; Description: "Abrir Image Studio"; Flags: nowait postinstall skipifsilent
```

`scripts/build.ps1`:
```powershell
# Construye dist\ImageStudio con PyInstaller, lo verifica y arma el instalador con Inno Setup 6.
# Uso: .\scripts\build.ps1            (ejecutable e instalador)
#      .\scripts\build.ps1 -SinInstalador
param([switch]$SinInstalador)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$version = & $python -X utf8 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

& $python -m PyInstaller --noconfirm --log-level WARN --distpath dist --workpath build packaging\image_studio.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }
& dist\ImageStudio\image-studio-cli.exe diagnostico
if ($LASTEXITCODE -ne 0) { throw "El diagnóstico del ejecutable falló" }
if ($SinInstalador) { return }

$candidatos = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)
$iscc = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "No se encontró Inno Setup 6 (winget install --id JRSoftware.InnoSetup -e)" }
& $iscc "/DVersion=$version" packaging\instalador.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló" }
Get-Item "dist\instalador\ImageStudio-Setup-$version.exe" | Select-Object Name, @{n = "MB"; e = { [int]($_.Length / 1MB) } }
```

**Paso 3 - Construir:**
```powershell
.\scripts\build.ps1
```
Esperado: diagnóstico correcto y `dist\instalador\ImageStudio-Setup-0.3.0.exe` (la versión sube
a 0.4.0 en la publicación). Anotar su tamaño; si supera 2 GB no se puede adjuntar a un release de
GitHub y se documenta dónde queda.

**Commit:**
```powershell
git add packaging/instalador.iss scripts/build.ps1
git commit -m "build(repo): agregar instalador por usuario y script de construccion"
```

### Tarea 12: documentación de uso

**Archivos:** modificar `README.md`

Agregar al final de `README.md`:
````markdown

## Instalador (Hito 4)

`ImageStudio-Setup-X.Y.Z.exe` instala la app para el usuario actual, sin permisos de
administrador, en `%LOCALAPPDATA%\Programs\Image Studio`. Durante la instalación prepara el motor
de recorte (hasta un minuto). Los modelos se descargan al primer uso a
`%LOCALAPPDATA%\ImageStudio\models`.

Requisitos mínimos: Windows 10/11 de 64 bits, 8 GB de RAM y 4 GB libres en disco. Con una GPU
NVIDIA de 8 GB o más la app usa BiRefNet en GPU (unos 5 s por foto); en otros equipos usa
BiRefNet liviano en CPU (unos 15 s). El equipo detectado y la elección aparecen en la barra de
estado; `image-studio-cli.exe diagnostico` muestra el detalle.

Construir el instalador:

```powershell
.\scripts\build.ps1
```
````

Sin test. **Commit:**
```powershell
git add README.md
git commit -m "docs(repo): documentar instalador y requisitos"
```

---

## Fase D - Verificación y publicación

### Tarea 13: probar el instalador y publicar 0.4.0

Sin archivos nuevos.

**Paso 1 - Suite completa** (`$LASTEXITCODE` igual a 0):
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```

**Paso 2 - Instalar en este PC** y verificar:
```powershell
dist\instalador\ImageStudio-Setup-0.3.0.exe /VERYSILENT /SUPPRESSMSGBOXES
& "$env:LOCALAPPDATA\Programs\Image Studio\image-studio-cli.exe" diagnostico
```
Esperado: `birefnet en GPU` y la prueba de recorte. Abrir la app desde el menú Inicio: arranca en
pocos segundos (el motor ya quedó preparado). Desinstalar desde "Agregar o quitar programas" y
comprobar que la carpeta del programa desaparece y los modelos se conservan.

**Paso 3 - Probar en un entorno sin GPU NVIDIA ni Python.** Opciones, en orden de preferencia:
Windows Sandbox (requiere que el usuario active la característica de Windows y reinicie) u otra
cuenta de usuario de Windows creada por el usuario. Esperado en Windows Sandbox: el diagnóstico
muestra `Sin GPU NVIDIA` y `birefnet_lite en CPU`, descarga el modelo y la prueba de recorte
termina. Anotar tiempos.

**Paso 4 - Publicar** siguiendo [../repo-workflow.md](../repo-workflow.md):
1. PR de `feature/hito-4-empaquetado` a `develop` (squash).
2. Rama `agent/release-0.4.0`: versión 0.4.0 en `pyproject.toml` y entrada en `CHANGELOG.md`;
   PR a `develop` (squash).
3. Reconstruir con `.\scripts\build.ps1` desde `develop` para obtener
   `ImageStudio-Setup-0.4.0.exe`.
4. PR de `develop` a `main` (merge commit) y etiqueta `v0.4.0`.
5. `gh release create v0.4.0 dist\instalador\ImageStudio-Setup-0.4.0.exe` si el archivo pesa menos
   de 2 GB; si no, crear el release sin adjunto e indicar en las notas dónde está el instalador.

---

## Cobertura del objetivo

| Requisito | Tarea |
|---|---|
| Un solo instalador con CUDA | 9, 10, 11 |
| Elegir modelo y dispositivo según el equipo | 3, 4, 5, 6 |
| BiRefNet liviano como modelo intermedio | 2 |
| Si la GPU falla, seguir en CPU y avisar | 5, 6 |
| Mostrar qué se está usando | 6, 7, 8 |
| Primer arranque sin congelar la ventana | 7, 11 |
| Requisitos mínimos documentados | 1, 12 |
| Probado en un equipo sin GPU NVIDIA | 13 |
