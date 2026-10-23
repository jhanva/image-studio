# Plan de implementación - Hito 3: suite

Spec: [../spec.md](../spec.md). Flujo: [../repo-workflow.md](../repo-workflow.md).
Hitos anteriores: [hito-1-motor.md](hito-1-motor.md), [hito-2-editor.md](hito-2-editor.md).
Rama: `feature/hito-3-suite` desde `develop`. Un commit por tarea; PR a `develop` (squash) al final.

## Objetivo del hito

Convertir el editor en una suite con herramientas intercambiables y completar el MVP:

- Ventana con barra lateral de herramientas (interfaz `Tool`): **Quitar fondo** (el editor del
  Hito 2) y **Lotes**.
- Panel de lotes en la interfaz: carpetas, preset, exportación, progreso, cancelación y tabla de
  resultados; doble clic abre la imagen en el editor (spec 3.5, punto 4 de Lote).
- Presets propios guardados en `%APPDATA%\ImageStudio\presets.json`, usables en editor y lotes.
- Diálogo de exportación completo: formato, fondo, color, recorte, margen y DPI.
- Un solo caché de modelos compartido por las herramientas.

## Decisión sobre ViTMatte (riesgo R1)

El modelo `hustvl/vitmatte-small-composition-1k` declara Apache-2.0, pero sus pesos se
entrenaron con Composition-1k de Adobe. Una fuente secundaria (ficha de
`LibreYOLO/LibreViTMattes-matte`) indica que la licencia de ese dataset limita los modelos
entrenados con él a uso no comercial; no se encontró el texto oficial de Adobe. Como los
resultados se usan en productos que se venden, **ViTMatte no se adopta**: el matting sigue
siendo el clásico de pymatting (MIT). Se reevalúa si aparecen pesos entrenados con datos de
licencia comercial.

## Datos verificados (2026-10-23, PySide6-Essentials 6.12.0)

| Dato | Resultado |
|---|---|
| Iconos estándar `SP_DirOpenIcon`, `SP_FileDialogDetailedView`, `SP_DialogSaveButton`, `SP_MediaPlay`, `SP_MediaStop`, `SP_BrowserReload` | Disponibles en estilo Fusion |
| `QListWidgetItem.setData(UserRole, ...)`, `QTableWidget.insertRow`, `QDialogButtonBox` | Funcionan en Python 3.14 |
| `%APPDATA%` | `C:\Users\Usuario\AppData\Roaming` |

## Mapa de archivos

- Modificar: `docs/spec.md`, `tests/conftest.py`, `src/image_studio/workers/tasks.py`,
  `src/image_studio/ui/main_window.py` (pasa a ser la ventana de la suite),
  `src/image_studio/ui/app.py`, `README.md`
- Crear (sin Qt): `src/image_studio/pipeline/presets_store.py`,
  `src/image_studio/pipeline/remover_cache.py`
- Crear (Qt): `src/image_studio/ui/export_dialog.py`, `src/image_studio/ui/preset_dialog.py`,
  `src/image_studio/tools/__init__.py`, `tools/base.py`, `tools/background_removal/__init__.py`,
  `tools/background_removal/editor.py`, `tools/batch/__init__.py`, `tools/batch/panel.py`
- Tests nuevos: `tests/pipeline/test_presets_store.py`, `tests/pipeline/test_remover_cache.py`,
  `tests/ui/test_export_dialog.py`, `tests/ui/test_preset_dialog.py`, `tests/tools/test_base.py`,
  `tests/tools/test_editor.py`, `tests/tools/test_batch.py`
- Tests modificados: `tests/workers/test_tasks.py`, `tests/ui/test_main_window.py`,
  `tests/ui/test_app.py`

Las rutas `tools/...` son relativas a `src/image_studio/`. Los `__init__.py` nuevos se crean
vacíos. Comandos desde la raíz del repo en PowerShell; cada commit solo después de ver el test
en verde (`$LASTEXITCODE` igual a 0).

---

## Fase A - Datos y tareas

### Tarea 1: actualizar la spec

**Archivos:** modificar `docs/spec.md`

Sin test (documental). Cambios exactos:

1. Tabla 3.2, fila de matting de borde: reemplazar el texto de la columna Uso
   `Pelo, pelaje, semitransparencias. Se integra cuando se resuelva R1; mientras tanto se usa el matting clásico`
   por `No adoptado (ver R1): los pesos públicos se entrenaron con Composition-1k, de uso no comercial`.
2. Tabla 5, fila R1: reemplazar la columna Mitigación por
   `Resuelto en el Hito 3: ViTMatte no se adopta y el matting es el clásico de pymatting (MIT). Se reevalúa si aparecen pesos con datos de licencia comercial`.
3. Árbol 3.4: bajo `pipeline/`, después de `refine_region.py`, agregar
   `      presets_store.py    # presets propios en %APPDATA%\ImageStudio\presets.json` y
   `      remover_cache.py    # un removedor por modelo, compartido por las herramientas`.
   Reemplazar el bloque `tools/` (tres líneas, desde `    tools/` hasta `background_removal/ # herramienta 1...`) por:
   ```
       tools/
         base.py             # Tool: QWidget con id, nombre, icono y mensajes de estado
         background_removal/ # herramienta 1: editor (Hito 2) con presets y exportación
         batch/              # herramienta 2: lotes con progreso, cancelación y tabla
   ```
   Reemplazar `      main_window.py      # acciones, barra de herramientas y estado` por
   `      main_window.py      # ventana de la suite: barra lateral de herramientas y estado`,
   y las líneas `      batch_panel.py      # Hito 3` y `      export_dialog.py    # Hito 3` por
   `      export_dialog.py    # formato, fondo, color, recorte, margen y DPI` y
   `      preset_dialog.py    # crear presets propios`.

**Verificar:**
```powershell
Select-String -Path docs\spec.md -Pattern "No adoptado","Resuelto en el Hito 3","presets_store.py","remover_cache.py","preset_dialog.py","batch/  "
```
Esperado: 6 coincidencias.

**Commit:**
```powershell
git add docs/spec.md
git commit -m "docs(spec): descartar vitmatte y definir la suite del hito 3"
```

### Tarea 2: presets propios

**Archivos:** crear `src/image_studio/pipeline/presets_store.py`,
`tests/pipeline/test_presets_store.py`; modificar `tests/conftest.py`

**Paso 1 - Tests que fallan.** Agregar al final de `tests/conftest.py`:
```python


@pytest.fixture(autouse=True)
def config_temporal(tmp_path, monkeypatch):
    """Ningún test escribe en el %APPDATA% real."""
    monkeypatch.setenv("IMAGE_STUDIO_CONFIG_DIR", str(tmp_path / "config"))
```

`tests/pipeline/test_presets_store.py`:
```python
import json

import pytest

from image_studio.pipeline.presets_store import PresetStore, config_dir
from image_studio.pipeline.settings import PRESETS, PipelineSettings


def test_la_carpeta_de_configuracion_respeta_la_variable(tmp_path):
    assert config_dir() == tmp_path / "config"


def test_sin_archivo_solo_hay_presets_incluidos():
    almacen = PresetStore()
    assert almacen.todos() == PRESETS
    assert almacen.propios() == {}


def test_guardar_y_releer():
    PresetStore().guardar("Camisetas ñ", PipelineSettings(modelo="isnet", banda_px=6))
    releido = PresetStore().todos()
    assert releido["Camisetas ñ"] == PipelineSettings(modelo="isnet", banda_px=6)
    assert list(releido)[: len(PRESETS)] == list(PRESETS)


def test_archivo_en_utf8(tmp_path):
    PresetStore().guardar("Camisetas ñ", PipelineSettings())
    texto = (tmp_path / "config" / "presets.json").read_text(encoding="utf-8")
    assert json.loads(texto)["presets"]["Camisetas ñ"]["modelo"] == "birefnet"


def test_nombres_invalidos():
    almacen = PresetStore()
    with pytest.raises(ValueError):
        almacen.guardar("  ", PipelineSettings())
    with pytest.raises(ValueError):
        almacen.guardar("producto", PipelineSettings())


def test_borrar():
    almacen = PresetStore()
    almacen.guardar("x", PipelineSettings())
    almacen.borrar("x")
    assert "x" not in almacen.todos()
    with pytest.raises(ValueError):
        almacen.borrar("persona")


def test_archivo_corrupto_no_rompe(tmp_path):
    ruta = tmp_path / "config" / "presets.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{no es json", encoding="utf-8")
    assert PresetStore().todos() == PRESETS


def test_entrada_invalida_se_ignora(tmp_path):
    ruta = tmp_path / "config" / "presets.json"
    ruta.parent.mkdir(parents=True)
    datos = {"version": 1, "presets": {"malo": {"modelo": "u2net"}, "bueno": {"banda_px": 4}}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert set(PresetStore().propios()) == {"bueno"}
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_presets_store.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.presets_store'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/presets_store.py`:
```python
"""Presets propios guardados en la carpeta de configuración del usuario."""

from __future__ import annotations

import json
import os
from pathlib import Path

from image_studio.pipeline.settings import PRESETS, PipelineSettings

VERSION = 1


def config_dir() -> Path:
    personalizado = os.environ.get("IMAGE_STUDIO_CONFIG_DIR")
    if personalizado:
        return Path(personalizado)
    return Path(os.environ["APPDATA"]) / "ImageStudio"


class PresetStore:
    def __init__(self, ruta: Path | None = None):
        self.ruta = ruta or config_dir() / "presets.json"

    def todos(self) -> dict[str, PipelineSettings]:
        """Incluidos primero, luego los propios en orden alfabético."""
        return {**PRESETS, **dict(sorted(self.propios().items()))}

    def propios(self) -> dict[str, PipelineSettings]:
        propios = {}
        for nombre, datos in self._leer().items():
            try:
                propios[nombre] = PipelineSettings.from_dict(datos)
            except (TypeError, ValueError):
                continue  # una entrada editada a mano o de una versión vieja no impide abrir la app
        return propios

    def guardar(self, nombre: str, ajustes: PipelineSettings) -> str:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El preset necesita un nombre")
        if nombre in PRESETS:
            raise ValueError(f"'{nombre}' es un preset incluido")
        datos = self._leer()
        datos[nombre] = ajustes.to_dict()
        self._escribir(datos)
        return nombre

    def borrar(self, nombre: str) -> None:
        if nombre in PRESETS:
            raise ValueError(f"'{nombre}' es un preset incluido")
        datos = self._leer()
        datos.pop(nombre, None)
        self._escribir(datos)

    def _leer(self) -> dict:
        try:
            contenido = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        presets = contenido.get("presets") if isinstance(contenido, dict) else None
        return {k: v for k, v in presets.items() if isinstance(v, dict)} if isinstance(presets, dict) else {}

    def _escribir(self, presets: dict) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_name(self.ruta.name + ".tmp")
        texto = json.dumps({"version": VERSION, "presets": presets}, ensure_ascii=False, indent=2)
        temporal.write_text(texto + "\n", encoding="utf-8", newline="\n")
        temporal.replace(self.ruta)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `8 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/presets_store.py tests/pipeline/test_presets_store.py tests/conftest.py
git commit -m "feat(pipeline): guardar presets propios en la configuracion del usuario"
```

### Tarea 3: caché de removedores compartido

**Archivos:** crear `src/image_studio/pipeline/remover_cache.py`,
`tests/pipeline/test_remover_cache.py`

**Paso 1 - Tests que fallan:**
```python
import threading
import time

from image_studio.pipeline.remover_cache import RemoverCache


def test_crea_una_vez_por_modelo_y_dispositivo():
    llamadas = []
    cache = RemoverCache(lambda modelo, dispositivo, progreso: llamadas.append((modelo, dispositivo)) or object())
    a = cache.get("birefnet")
    assert cache.get("birefnet") is a
    cache.get("isnet")
    cache.get("birefnet", "cpu")
    assert llamadas == [("birefnet", "auto"), ("isnet", "auto"), ("birefnet", "cpu")]


def test_hilos_simultaneos_cargan_el_modelo_una_sola_vez():
    llamadas = []

    def crear(modelo, dispositivo, progreso):
        llamadas.append(modelo)
        time.sleep(0.05)
        return object()

    cache = RemoverCache(crear)
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(cache.get("birefnet"))) for _ in range(5)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert llamadas == ["birefnet"]
    assert len({id(r) for r in resultados}) == 1
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/pipeline/test_remover_cache.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.pipeline.remover_cache'`.

**Paso 3 - Implementar** `src/image_studio/pipeline/remover_cache.py`:
```python
"""Un removedor por modelo y dispositivo, compartido por todas las herramientas."""

from __future__ import annotations

import threading

from image_studio.pipeline.factory import build_remover


class RemoverCache:
    def __init__(self, crear=build_remover):
        self._crear = crear
        self._removedores: dict[tuple[str, str], object] = {}
        # Cargar BiRefNet tarda unos 11 s; el candado evita cargarlo dos veces si el editor y
        # el panel de lotes lo piden a la vez.
        self._candado = threading.Lock()

    def get(self, modelo: str, dispositivo: str = "auto", progreso=None):
        clave = (modelo, dispositivo)
        with self._candado:
            if clave not in self._removedores:
                self._removedores[clave] = self._crear(modelo, dispositivo, progreso)
            return self._removedores[clave]
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `2 passed`.

**Commit:**
```powershell
git add src/image_studio/pipeline/remover_cache.py tests/pipeline/test_remover_cache.py
git commit -m "feat(pipeline): compartir removedores entre herramientas"
```

### Tarea 4: avance en las tareas de segundo plano

**Archivos:** modificar `src/image_studio/workers/tasks.py`, `tests/workers/test_tasks.py`

**Paso 1 - Test que falla.** Agregar al final de `tests/workers/test_tasks.py`:
```python


def test_reporta_avance_antes_del_resultado(qtbot):
    eventos = []

    def contar(hasta, reportar):
        for i in range(1, hasta + 1):
            reportar(i)
        return "listo"

    ejecutar(
        contar,
        3,
        al_terminar=eventos.append,
        al_fallar=eventos.append,
        al_avanzar=eventos.append,
    )
    qtbot.waitUntil(lambda: "listo" in eventos)
    assert eventos == [1, 2, 3, "listo"]
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/workers/test_tasks.py -q
```
Esperado: `TypeError: ejecutar() got an unexpected keyword argument 'al_avanzar'`.

**Paso 3 - Implementar.** Reemplazar `src/image_studio/workers/tasks.py` por:
```python
"""Ejecutar funciones en el QThreadPool y recibir el resultado en el hilo principal."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Senales(QObject):
    listo = Signal(object)
    fallo = Signal(str)
    avance = Signal(object)


class Tarea(QRunnable):
    def __init__(self, funcion: Callable, *args, con_avance: bool = False):
        super().__init__()
        self.funcion = funcion
        self.args = args
        self.con_avance = con_avance
        self.senales = _Senales()

    def run(self) -> None:
        try:
            if self.con_avance:
                resultado = self.funcion(*self.args, reportar=self.senales.avance.emit)
            else:
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
    al_avanzar: Callable[[object], None] | None = None,
    pool: QThreadPool | None = None,
) -> Tarea:
    """Si se pasa al_avanzar, la función recibe reportar=callable para enviar avances."""
    tarea = Tarea(funcion, *args, con_avance=al_avanzar is not None)
    _activas.add(tarea)
    if al_avanzar is not None:
        tarea.senales.avance.connect(al_avanzar)
    tarea.senales.listo.connect(lambda resultado: (_activas.discard(tarea), al_terminar(resultado)))
    tarea.senales.fallo.connect(lambda mensaje: (_activas.discard(tarea), al_fallar(mensaje)))
    (pool or QThreadPool.globalInstance()).start(tarea)
    return tarea
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/workers/tasks.py tests/workers/test_tasks.py
git commit -m "feat(workers): reportar avance desde tareas en segundo plano"
```

---

## Fase B - Diálogos

### Tarea 5: diálogo de exportación

**Archivos:** crear `src/image_studio/ui/export_dialog.py`, `tests/ui/test_export_dialog.py`

**Paso 1 - Tests que fallan:**
```python
from image_studio.core.export import ExportSettings, Fondo
from image_studio.ui.export_dialog import ExportDialog


def test_valores_iniciales_de_ida_y_vuelta(qtbot):
    ajustes = ExportSettings(formato="webp", fondo=Fondo.COLOR, color=(10, 20, 30), recortar=True, margen_px=40, dpi=300)
    dialogo = ExportDialog(ajustes)
    qtbot.addWidget(dialogo)
    assert dialogo.ajustes() == ajustes


def test_cambiar_campos(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    dialogo.combo_formato.setCurrentText("jpg")
    dialogo.combo_fondo.setCurrentText("blanco")
    dialogo.check_recortar.setChecked(True)
    dialogo.spin_margen.setValue(25)
    dialogo.spin_dpi.setValue(150)
    assert dialogo.ajustes() == ExportSettings(formato="jpg", fondo=Fondo.BLANCO, recortar=True, margen_px=25, dpi=150)


def test_margen_solo_con_recorte(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert not dialogo.spin_margen.isEnabled()
    dialogo.check_recortar.setChecked(True)
    assert dialogo.spin_margen.isEnabled()


def test_dpi_cero_es_sin_cambio(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    dialogo.spin_dpi.setValue(0)
    assert dialogo.ajustes().dpi is None


def test_aviso_jpg_transparente(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert dialogo.aviso.isHidden()
    dialogo.combo_formato.setCurrentText("jpg")
    assert not dialogo.aviso.isHidden()


def test_color_solo_con_fondo_de_color(qtbot):
    dialogo = ExportDialog()
    qtbot.addWidget(dialogo)
    assert not dialogo.boton_color.isEnabled()
    dialogo.combo_fondo.setCurrentText("color")
    dialogo.set_color((1, 2, 3))
    assert dialogo.boton_color.isEnabled()
    assert dialogo.ajustes().color == (1, 2, 3)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_export_dialog.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.export_dialog'`.

**Paso 3 - Implementar** `src/image_studio/ui/export_dialog.py`:
```python
"""Diálogo de exportación: formato, fondo, color, recorte, margen y DPI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from image_studio.core.export import FORMATOS_SALIDA, ExportSettings, Fondo


class ExportDialog(QDialog):
    def __init__(self, ajustes: ExportSettings | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar")
        ajustes = ajustes or ExportSettings()
        self._color = ajustes.color

        self.combo_formato = QComboBox()
        self.combo_formato.addItems(list(FORMATOS_SALIDA))
        self.combo_formato.setCurrentText(ajustes.formato)
        self.combo_fondo = QComboBox()
        self.combo_fondo.addItems([f.value for f in Fondo])
        self.combo_fondo.setCurrentText(ajustes.fondo.value)
        self.boton_color = QPushButton()
        self.boton_color.clicked.connect(self._elegir_color)
        self.check_recortar = QCheckBox("Recortar al contenido")
        self.check_recortar.setChecked(ajustes.recortar)
        self.spin_margen = QSpinBox()
        self.spin_margen.setRange(0, 2000)
        self.spin_margen.setSuffix(" px")
        self.spin_margen.setValue(ajustes.margen_px)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(0, 2400)
        self.spin_dpi.setSpecialValueText("Sin cambiar")
        self.spin_dpi.setValue(ajustes.dpi or 0)
        self.aviso = QLabel("JPG no admite transparencia: se exporta con fondo blanco.")
        self.aviso.setWordWrap(True)

        formulario = QFormLayout()
        formulario.addRow("Formato", self.combo_formato)
        formulario.addRow("Fondo", self.combo_fondo)
        formulario.addRow("Color", self.boton_color)
        formulario.addRow("", self.check_recortar)
        formulario.addRow("Margen", self.spin_margen)
        formulario.addRow("DPI", self.spin_dpi)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self.aviso)
        diseno.addWidget(botones)

        for senal in (self.combo_formato.currentTextChanged, self.combo_fondo.currentTextChanged):
            senal.connect(self._actualizar)
        self.check_recortar.toggled.connect(self._actualizar)
        self._actualizar()

    def ajustes(self) -> ExportSettings:
        return ExportSettings(
            formato=self.combo_formato.currentText(),
            fondo=Fondo(self.combo_fondo.currentText()),
            color=self._color,
            recortar=self.check_recortar.isChecked(),
            margen_px=self.spin_margen.value(),
            dpi=self.spin_dpi.value() or None,
        )

    def set_color(self, color: tuple[int, int, int]) -> None:
        self._color = tuple(color)
        self._actualizar()

    def _elegir_color(self) -> None:
        elegido = QColorDialog.getColor(QColor(*self._color), self, "Color de fondo")
        if elegido.isValid():
            self.set_color((elegido.red(), elegido.green(), elegido.blue()))

    def _actualizar(self, *_) -> None:
        r, g, b = self._color
        self.boton_color.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.boton_color.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
        self.boton_color.setEnabled(self.combo_fondo.currentText() == Fondo.COLOR.value)
        self.spin_margen.setEnabled(self.check_recortar.isChecked())
        transparente_en_jpg = (
            self.combo_formato.currentText() == "jpg"
            and self.combo_fondo.currentText() == Fondo.TRANSPARENTE.value
        )
        self.aviso.setHidden(not transparente_en_jpg)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `6 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/export_dialog.py tests/ui/test_export_dialog.py
git commit -m "feat(ui): agregar dialogo de exportacion"
```

### Tarea 6: diálogo para crear presets

**Archivos:** crear `src/image_studio/ui/preset_dialog.py`, `tests/ui/test_preset_dialog.py`

**Paso 1 - Tests que fallan:**
```python
from PySide6.QtWidgets import QDialogButtonBox

from image_studio.pipeline.settings import PRESETS, PipelineSettings
from image_studio.ui.preset_dialog import PresetDialog


def _ok(dialogo):
    return dialogo.botones.button(QDialogButtonBox.StandardButton.Ok)


def test_parte_del_preset_base(qtbot):
    base = PipelineSettings(modelo="isnet", matting=False, banda_px=7, desplazamiento_px=-2, suavizado_px=1.5)
    dialogo = PresetDialog(base, set(PRESETS))
    qtbot.addWidget(dialogo)
    dialogo.edit_nombre.setText("Tazas")
    assert dialogo.valor() == ("Tazas", base)


def test_nombre_vacio_o_reservado_no_se_acepta(qtbot):
    dialogo = PresetDialog(PipelineSettings(), set(PRESETS))
    qtbot.addWidget(dialogo)
    assert not _ok(dialogo).isEnabled()
    dialogo.edit_nombre.setText("producto")
    assert not _ok(dialogo).isEnabled()
    assert "incluido" in dialogo.error.text()
    dialogo.edit_nombre.setText("Tazas")
    assert _ok(dialogo).isEnabled() and dialogo.error.text() == ""


def test_cambiar_campos(qtbot):
    dialogo = PresetDialog(PipelineSettings(), set(PRESETS))
    qtbot.addWidget(dialogo)
    dialogo.edit_nombre.setText(" Gorras ")
    dialogo.combo_modelo.setCurrentText("isnet")
    dialogo.check_matting.setChecked(False)
    dialogo.check_limpieza.setChecked(False)
    dialogo.spin_banda.setValue(4)
    dialogo.spin_desplazamiento.setValue(3)
    dialogo.spin_suavizado.setValue(0.5)
    assert dialogo.valor() == (
        "Gorras",
        PipelineSettings(modelo="isnet", matting=False, limpieza_color=False, banda_px=4, desplazamiento_px=3, suavizado_px=0.5),
    )
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_preset_dialog.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.ui.preset_dialog'`.

**Paso 3 - Implementar** `src/image_studio/ui/preset_dialog.py`:
```python
"""Diálogo para crear un preset propio a partir de otro."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from image_studio.pipeline.settings import MODELOS_SEGMENTACION, PipelineSettings


class PresetDialog(QDialog):
    def __init__(self, base: PipelineSettings, reservados: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guardar preset")
        self._reservados = reservados
        self.edit_nombre = QLineEdit()
        self.combo_modelo = QComboBox()
        self.combo_modelo.addItems(list(MODELOS_SEGMENTACION))
        self.combo_modelo.setCurrentText(base.modelo)
        self.check_matting = QCheckBox("Matting de borde")
        self.check_matting.setChecked(base.matting)
        self.check_limpieza = QCheckBox("Limpieza de color")
        self.check_limpieza.setChecked(base.limpieza_color)
        self.spin_banda = QSpinBox()
        self.spin_banda.setRange(1, 100)
        self.spin_banda.setSuffix(" px")
        self.spin_banda.setValue(base.banda_px)
        self.spin_desplazamiento = QSpinBox()
        self.spin_desplazamiento.setRange(-50, 50)
        self.spin_desplazamiento.setSuffix(" px")
        self.spin_desplazamiento.setValue(base.desplazamiento_px)
        self.spin_suavizado = QDoubleSpinBox()
        self.spin_suavizado.setRange(0.0, 20.0)
        self.spin_suavizado.setSingleStep(0.5)
        self.spin_suavizado.setSuffix(" px")
        self.spin_suavizado.setValue(base.suavizado_px)
        self.error = QLabel("")

        formulario = QFormLayout()
        formulario.addRow("Nombre", self.edit_nombre)
        formulario.addRow("Modelo", self.combo_modelo)
        formulario.addRow("", self.check_matting)
        formulario.addRow("", self.check_limpieza)
        formulario.addRow("Banda de matting", self.spin_banda)
        formulario.addRow("Desplazar borde", self.spin_desplazamiento)
        formulario.addRow("Suavizar borde", self.spin_suavizado)
        self.botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self.error)
        diseno.addWidget(self.botones)
        self.edit_nombre.textChanged.connect(self._validar)
        self._validar()

    def valor(self) -> tuple[str, PipelineSettings]:
        return self.edit_nombre.text().strip(), PipelineSettings(
            modelo=self.combo_modelo.currentText(),
            matting=self.check_matting.isChecked(),
            limpieza_color=self.check_limpieza.isChecked(),
            banda_px=self.spin_banda.value(),
            desplazamiento_px=self.spin_desplazamiento.value(),
            suavizado_px=self.spin_suavizado.value(),
        )

    def _validar(self, *_) -> None:
        nombre = self.edit_nombre.text().strip()
        mensaje = ""
        if nombre in self._reservados:
            mensaje = f"'{nombre}' es un preset incluido; usa otro nombre."
        self.error.setText(mensaje)
        valido = bool(nombre) and not mensaje
        self.botones.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valido)
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/preset_dialog.py tests/ui/test_preset_dialog.py
git commit -m "feat(ui): agregar dialogo para crear presets"
```

---

## Fase C - Herramientas

### Tarea 7: interfaz `Tool`

**Archivos:** crear `src/image_studio/tools/__init__.py`, `src/image_studio/tools/base.py`,
`tests/tools/test_base.py`

**Paso 1 - Tests que fallan:**
```python
from PySide6.QtWidgets import QStyle

from image_studio.tools.base import Tool


class Prueba(Tool):
    id = "prueba"
    nombre = "Prueba"
    icono_estandar = QStyle.StandardPixmap.SP_DirOpenIcon


def test_icono_y_datos(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    assert herramienta.id == "prueba" and herramienta.nombre == "Prueba"
    assert not herramienta.icono().isNull()


def test_informar_emite_y_recuerda(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    recibidos = []
    herramienta.mensaje.connect(recibidos.append)
    herramienta.informar("hola")
    assert recibidos == ["hola"] and herramienta.ultimo_mensaje == "hola"


def test_detener_por_defecto_no_hace_nada(qtbot):
    herramienta = Prueba()
    qtbot.addWidget(herramienta)
    herramienta.detener()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/tools/test_base.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.tools'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/tools/__init__.py` y
`src/image_studio/tools/base.py`:
```python
"""Interfaz de las herramientas de la suite."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QWidget


class Tool(QWidget):
    """Un panel de la suite. La ventana lo muestra en la barra lateral y escucha sus mensajes."""

    id: str = ""
    nombre: str = ""
    icono_estandar = QStyle.StandardPixmap.SP_FileIcon
    mensaje = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ultimo_mensaje = ""

    def icono(self) -> QIcon:
        return self.style().standardIcon(self.icono_estandar)

    def informar(self, texto: str) -> None:
        self.ultimo_mensaje = texto
        self.mensaje.emit(texto)

    def detener(self) -> None:
        """Pide cancelar el trabajo en curso antes de cerrar la ventana."""
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `3 passed`.

**Commit:**
```powershell
git add src/image_studio/tools/__init__.py src/image_studio/tools/base.py tests/tools/test_base.py
git commit -m "feat(tools): definir la interfaz de herramientas de la suite"
```

### Tarea 8: el editor como herramienta

**Archivos:** crear `src/image_studio/tools/background_removal/__init__.py`,
`src/image_studio/tools/background_removal/editor.py`, `tests/tools/test_editor.py`

Refactor: el código de edición sale de `MainWindow` hacia `EditorTool`. `main_window.py` no se
toca en esta tarea (se reemplaza en la tarea 9); durante una tarea conviven ambos.

**Paso 1 - Tests que fallan.** `tests/tools/test_editor.py` (los casos de
`tests/ui/test_main_window.py` adaptados a la herramienta, más presets propios en el combo):
```python
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remove_bg import RemovalResult
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.settings import PipelineSettings
from image_studio.tools.background_removal.editor import EditorTool


class RemovedorFijo:
    def __init__(self):
        self.ajustes = []

    def run(self, doc, ajustes, usar_alfa_existente=False):
        self.ajustes.append(ajustes)
        alfa = np.zeros(doc.rgb.shape[:2], np.float32)
        alfa[20:80, 20:80] = 1.0
        return RemovalResult(doc.rgb, alfa, None, False, "", {"segmentacion": 0.01})


class MatterFijo:
    nombre = "fijo"

    def refine(self, rgb, trimap, grueso):
        return np.full(grueso.shape, 0.42, np.float32)


@pytest.fixture
def removedor():
    return RemovedorFijo()


@pytest.fixture
def editor(qtbot, removedor):
    cache = RemoverCache(lambda modelo, dispositivo, progreso: removedor)
    editor = EditorTool(cache, PresetStore(), matter=MatterFijo())
    qtbot.addWidget(editor)
    editor.resize(800, 600)
    editor.show()
    return editor


@pytest.fixture
def abierto(editor, escribir_png, tmp_path):
    assert editor.abrir(escribir_png(tmp_path / "foto.png", ancho=100, alto=100))
    return editor


def _trazo(editor, desde, hasta):
    editor._trazo_inicio(QPointF(*desde))
    editor._trazo_mueve(QPointF(*hasta))
    editor._trazo_fin()


def test_estado_inicial(editor):
    assert editor.id == "editor" and editor.sesion is None
    assert not editor.accion_quitar.isEnabled() and editor.accion_abrir.isEnabled()


def test_abrir_imagen(abierto):
    assert abierto.sesion.doc.size == (100, 100)
    assert "foto.png" in abierto.ultimo_mensaje
    assert abierto.accion_quitar.isEnabled()


def test_archivo_corrupto_muestra_error(editor, tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"x")
    assert not editor.abrir(ruta)
    assert "No se pudo leer" in editor.ultimo_mensaje
    assert editor.sesion is None


def test_quitar_fondo_en_segundo_plano(abierto, qtbot):
    abierto.quitar_fondo()
    assert abierto.ocupado
    qtbot.waitUntil(lambda: not abierto.ocupado)
    assert abierto.sesion.alpha[50, 50] == 1.0 and abierto.sesion.alpha[0, 0] == 0.0
    assert "Fondo quitado" in abierto.ultimo_mensaje


def test_usa_presets_propios(editor, escribir_png, tmp_path, removedor, qtbot):
    PresetStore().guardar("Tazas", PipelineSettings(matting=False, banda_px=4))
    editor.recargar_presets("Tazas")
    assert editor.combo_preset.currentText() == "Tazas"
    editor.abrir(escribir_png(tmp_path / "taza.png", ancho=100, alto=100))
    editor.quitar_fondo()
    qtbot.waitUntil(lambda: not editor.ocupado)
    assert removedor.ajustes[-1] == PipelineSettings(matting=False, banda_px=4)


def test_sin_herramienta_no_pinta(abierto):
    _trazo(abierto, (50, 50), (60, 50))
    assert (abierto.sesion.alpha == 1.0).all()


def test_borrar_y_deshacer(abierto):
    abierto.accion_borrar.trigger()
    abierto.spin_radio.setValue(5)
    abierto.spin_dureza.setValue(100)
    _trazo(abierto, (50, 50), (60, 50))
    assert abierto.sesion.alpha[50, 55] == 0.0
    assert abierto.accion_deshacer.isEnabled()
    abierto.deshacer()
    assert (abierto.sesion.alpha == 1.0).all()
    abierto.rehacer()
    assert abierto.sesion.alpha[50, 55] == 0.0


def test_refinar_corre_en_segundo_plano(abierto, qtbot):
    abierto.accion_refinar.trigger()
    abierto.spin_radio.setValue(5)
    _trazo(abierto, (50, 50), (60, 50))
    qtbot.waitUntil(lambda: not abierto.ocupado)
    assert abierto.sesion.alpha[50, 55] == pytest.approx(0.42)
    assert abierto.lienzo.ruta_refinar.isEmpty()
    abierto.deshacer()
    assert (abierto.sesion.alpha == 1.0).all()


def test_guardar_png(abierto, qtbot, tmp_path):
    abierto.quitar_fondo()
    qtbot.waitUntil(lambda: not abierto.ocupado)
    destino = abierto.guardar_en(tmp_path / "salida.png")
    with Image.open(destino) as imagen:
        alfa = np.array(imagen)[..., 3]
    assert alfa[0, 0] == 0 and alfa[50, 50] == 255


def test_pegar_desde_portapapeles(editor):
    imagen = QImage(30, 20, QImage.Format.Format_RGBA8888)
    imagen.fill(QColor(10, 20, 30, 255))
    QApplication.clipboard().setImage(imagen)
    editor.pegar()
    assert editor.sesion.doc.size == (30, 20)


def test_ver_original(abierto):
    abierto.accion_antes.trigger()
    assert abierto.lienzo.capa.mostrando_antes
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/tools/test_editor.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.tools.background_removal'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/tools/background_removal/__init__.py` y
`src/image_studio/tools/background_removal/editor.py`:
```python
"""Herramienta Quitar fondo: editor con pinceles, historial, presets y exportación."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QSpinBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
)

from image_studio.core.brush import Modo, Rect
from image_studio.core.export import ExportSettings
from image_studio.core.image_io import FORMATOS_ENTRADA, ImageDoc, ImageLoadError, load_image
from image_studio.engines.matting_classic import ClassicMatter
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.pipeline.session import EditSession, Pincel
from image_studio.pipeline.settings import PipelineSettings
from image_studio.tools.base import Tool
from image_studio.ui.canvas.view import CanvasView
from image_studio.ui.qt_image import RgbaBuffer, RgbBuffer, qimage_to_arrays
from image_studio.workers.tasks import ejecutar

FILTRO_IMAGENES = "Imágenes (" + " ".join(f"*{e}" for e in sorted(FORMATOS_ENTRADA)) + ")"


class EditorTool(Tool):
    id = "editor"
    nombre = "Quitar fondo"
    icono_estandar = QStyle.StandardPixmap.SP_FileDialogContentsView

    def __init__(self, cache: RemoverCache, presets: PresetStore, matter=None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._cache = cache
        self._presets = presets
        self._matter = matter if matter is not None else ClassicMatter()
        self.sesion: EditSession | None = None
        self._despues: RgbaBuffer | None = None
        self._antes: RgbBuffer | None = None
        self.ocupado = False
        self.barra = QToolBar("Editor")
        self.lienzo = CanvasView(self)
        self.lienzo.trazo_inicio.connect(self._trazo_inicio)
        self.lienzo.trazo_mueve.connect(self._trazo_mueve)
        self.lienzo.trazo_fin.connect(self._trazo_fin)
        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.barra)
        diseno.addWidget(self.lienzo)
        self._crear_interfaz()
        self._actualizar_estado()
        self.informar("Abre una imagen (Ctrl+O), arrástrala aquí o pégala (Ctrl+V)")

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
        self.recargar_presets("producto")
        self.spin_radio = QSpinBox()
        self.spin_radio.setRange(1, 500)
        self.spin_radio.setValue(30)
        self.spin_radio.valueChanged.connect(lambda valor: self.lienzo.set_brush_radius(float(valor)))
        self.spin_dureza = QSpinBox()
        self.spin_dureza.setRange(0, 100)
        self.spin_dureza.setValue(80)
        self.spin_dureza.setSuffix(" %")

        barra = self.barra
        barra.setMovable(False)
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

    def recargar_presets(self, seleccion: str | None = None) -> None:
        actual = seleccion or self.combo_preset.currentText()
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItems(list(self._presets.todos()))
        self.combo_preset.setCurrentText(actual)
        self.combo_preset.blockSignals(False)

    def _ajustes_actuales(self) -> PipelineSettings:
        return self._presets.todos()[self.combo_preset.currentText()]

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
        self.informar(mensaje)
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
            self.informar(str(exc))
            return False
        return self.cargar_doc(doc)

    def cargar_doc(self, doc: ImageDoc) -> bool:
        if self.ocupado:
            self.informar("Espera a que termine la tarea en curso")
            return False
        self.sesion = EditSession(doc)
        self._despues = RgbaBuffer(self.sesion.rgb, self.sesion.alpha)
        self._antes = RgbBuffer(doc.rgb)
        self.lienzo.set_images(self._despues.imagen, self._antes.imagen)
        self.accion_antes.setChecked(False)
        self.lienzo.capa.set_show_before(False)
        ancho, alto = doc.size
        self.informar(f"{doc.path.name}: {ancho}x{alto}")
        self._actualizar_estado()
        return True

    def cargar_qimage(self, imagen: QImage, nombre: str = "portapapeles.png") -> bool:
        rgb, alfa = qimage_to_arrays(imagen)
        return self.cargar_doc(ImageDoc(Path(nombre), rgb, alfa, None, None))

    def pegar(self) -> None:
        imagen = QApplication.clipboard().image()
        if imagen.isNull():
            self.informar("El portapapeles no tiene una imagen")
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
        self._ocupar(f"Quitando fondo ({self.combo_preset.currentText()})...")
        ejecutar(
            self._ejecutar_removedor,
            self.sesion.doc,
            self._ajustes_actuales(),
            al_terminar=self._fondo_quitado,
            al_fallar=self._tarea_fallida,
        )

    def _ejecutar_removedor(self, doc, ajustes):
        # Corre en un hilo de trabajo; la primera vez carga el modelo (BiRefNet tarda unos 11 s).
        return self._cache.get(ajustes.modelo).run(doc, ajustes)

    def _fondo_quitado(self, resultado) -> None:
        self._liberar()
        self._refrescar(self.sesion.apply_result(resultado))
        self._actualizar_estado()
        total = sum(resultado.tiempos.values())
        aviso = f" Revisar: {resultado.motivo_confianza}." if resultado.baja_confianza else ""
        self.informar(f"Fondo quitado en {total:.1f} s.{aviso}")

    def _tarea_fallida(self, mensaje: str) -> None:
        if self.sesion is not None and self.sesion.refinado_pendiente:
            self.sesion.cancel_refine()
            self.lienzo.limpiar_vista_refinar()
        self._liberar()
        self.informar(f"Error: {mensaje}")

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
        self.informar("Borde refinado")

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
        return self.exportar_en(ruta, ExportSettings())

    def exportar_en(self, ruta: Path, ajustes: ExportSettings) -> Path | None:
        if self.sesion is None or self.ocupado:
            return None
        limpiar = self.sesion.resultado is not None and self._ajustes_actuales().limpieza_color
        destino = self.sesion.export(ruta, ajustes, limpiar_color=limpiar)
        self.informar(f"Guardado: {destino}")
        return destino
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `11 passed`.

**Commit:**
```powershell
git add src/image_studio/tools/background_removal tests/tools/test_editor.py
git commit -m "refactor(tools): convertir el editor en herramienta de la suite"
```

### Tarea 9: ventana de la suite

**Archivos:** modificar `src/image_studio/ui/main_window.py`, `src/image_studio/ui/app.py`,
`tests/ui/test_main_window.py`, `tests/ui/test_app.py`

**Paso 1 - Tests que fallan.** Reemplazar `tests/ui/test_main_window.py` por:
```python
from PySide6.QtWidgets import QStyle

from image_studio.tools.base import Tool
from image_studio.ui.main_window import MainWindow


class Uno(Tool):
    id = "uno"
    nombre = "Uno"


class Dos(Tool):
    id = "dos"
    nombre = "Dos"
    icono_estandar = QStyle.StandardPixmap.SP_DirOpenIcon

    def __init__(self):
        super().__init__()
        self.detenida = False

    def detener(self):
        self.detenida = True


def _ventana(qtbot):
    herramientas = [Uno(), Dos()]
    ventana = MainWindow(herramientas)
    qtbot.addWidget(ventana)
    ventana.show()
    return ventana, herramientas


def test_lista_las_herramientas_y_muestra_la_primera(qtbot):
    ventana, (uno, _dos) = _ventana(qtbot)
    assert [ventana.lista.item(i).text() for i in range(ventana.lista.count())] == ["Uno", "Dos"]
    assert ventana.actual() is uno


def test_cambiar_de_herramienta(qtbot):
    ventana, (_uno, dos) = _ventana(qtbot)
    assert ventana.mostrar("dos") is dos
    assert ventana.actual() is dos and ventana.lista.currentRow() == 1
    ventana.lista.setCurrentRow(0)
    assert ventana.actual().id == "uno"


def test_mensajes_van_a_la_barra_de_estado(qtbot):
    ventana, (uno, _dos) = _ventana(qtbot)
    uno.informar("hola")
    assert ventana.statusBar().currentMessage() == "hola"


def test_cerrar_detiene_las_herramientas(qtbot):
    ventana, (_uno, dos) = _ventana(qtbot)
    ventana.close()
    assert dos.detenida
```

Reemplazar `tests/ui/test_app.py` por:
```python
from PySide6.QtGui import QPalette

from image_studio.ui.app import FONDO_VENTANA, aplicar_tema, crear_ventana


def test_tema_oscuro(qapp):
    aplicar_tema(qapp)
    assert qapp.style().name().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window) == FONDO_VENTANA


def test_crear_ventana_abre_la_imagen_en_el_editor(qtbot, escribir_png, tmp_path):
    ventana = crear_ventana([str(escribir_png(tmp_path / "a.png"))])
    qtbot.addWidget(ventana)
    assert ventana.actual().id == "editor"
    assert ventana.herramienta("editor").sesion is not None


def test_crear_ventana_sin_imagen(qtbot):
    ventana = crear_ventana([])
    qtbot.addWidget(ventana)
    assert ventana.herramienta("editor").sesion is None
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_main_window.py tests/ui/test_app.py -q
```
Esperado: `AttributeError: 'MainWindow' object has no attribute 'lista'` (la ventana vieja
acepta la lista como si fuera `crear_removedor`) y
`AttributeError: 'MainWindow' object has no attribute 'herramienta'`.

**Paso 3 - Implementar.** Reemplazar `src/image_studio/ui/main_window.py` por:
```python
"""Ventana de la suite: barra lateral de herramientas, panel activo y barra de estado."""

from __future__ import annotations

from PySide6.QtCore import QSize, QThreadPool
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from image_studio.tools.base import Tool


class MainWindow(QMainWindow):
    def __init__(self, herramientas: list[Tool]):
        super().__init__()
        self.setWindowTitle("Image Studio")
        self.resize(1400, 900)
        self._herramientas = list(herramientas)
        self.lista = QListWidget()
        self.lista.setFixedWidth(140)
        self.lista.setIconSize(QSize(24, 24))
        self.pila = QStackedWidget()
        for herramienta in self._herramientas:
            self.lista.addItem(QListWidgetItem(herramienta.icono(), herramienta.nombre))
            self.pila.addWidget(herramienta)
            herramienta.mensaje.connect(self.statusBar().showMessage)
        self.lista.currentRowChanged.connect(self._cambiar)
        central = QWidget()
        diseno = QHBoxLayout(central)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.setSpacing(0)
        diseno.addWidget(self.lista)
        diseno.addWidget(self.pila)
        self.setCentralWidget(central)
        self.lista.setCurrentRow(0)

    def herramienta(self, id_: str) -> Tool:
        return next(h for h in self._herramientas if h.id == id_)

    def actual(self) -> Tool:
        return self.pila.currentWidget()

    def mostrar(self, id_: str) -> Tool:
        herramienta = self.herramienta(id_)
        self.lista.setCurrentRow(self._herramientas.index(herramienta))
        return herramienta

    def _cambiar(self, fila: int) -> None:
        self.pila.setCurrentIndex(fila)
        self.statusBar().showMessage(self.actual().ultimo_mensaje)

    def closeEvent(self, evento) -> None:
        for herramienta in self._herramientas:
            herramienta.detener()
        # Un hilo de trabajo vivo al cerrar Python puede terminar el proceso con error.
        QThreadPool.globalInstance().waitForDone()
        super().closeEvent(evento)
```

En `src/image_studio/ui/app.py`:

1. Reemplazar la línea `from image_studio.ui.main_window import MainWindow` por:
   ```python
   from image_studio.pipeline.presets_store import PresetStore
   from image_studio.pipeline.remover_cache import RemoverCache
   from image_studio.tools.background_removal.editor import EditorTool
   from image_studio.tools.base import Tool
   from image_studio.ui.main_window import MainWindow
   ```
2. Reemplazar la función `crear_ventana` completa por:
   ```python
   def crear_herramientas(cache: RemoverCache | None = None, presets: PresetStore | None = None) -> list[Tool]:
       cache = cache or RemoverCache()
       presets = presets or PresetStore()
       return [EditorTool(cache, presets)]


   def crear_ventana(rutas: list[str]) -> MainWindow:
       herramientas = crear_herramientas()
       ventana = MainWindow(herramientas)
       if rutas:
           ventana.mostrar("editor").abrir(Path(rutas[0]))
       return ventana
   ```

**Paso 4 - Verificar que pasa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui tests/tools tests/test_main.py -q
```
Esperado: todo `passed` (4 de la ventana, 3 de la app y el resto de `tests/ui` y `tests/tools`).

**Commit:**
```powershell
git add src/image_studio/ui/main_window.py src/image_studio/ui/app.py tests/ui/test_main_window.py tests/ui/test_app.py
git commit -m "feat(ui): convertir la ventana en la suite con barra de herramientas"
```

### Tarea 10: presets propios y exportación en el editor

**Archivos:** modificar `src/image_studio/tools/background_removal/editor.py`,
`tests/tools/test_editor.py`

**Paso 1 - Tests que fallan.** Agregar al final de `tests/tools/test_editor.py`:
```python


def test_guardar_y_borrar_preset_propio(editor):
    editor.guardar_preset("Gorras", PipelineSettings(modelo="isnet"))
    assert editor.combo_preset.currentText() == "Gorras"
    assert "Gorras" in PresetStore().propios()
    assert editor.accion_borrar_preset.isEnabled()
    editor.borrar_preset("Gorras")
    assert "Gorras" not in PresetStore().propios()
    assert editor.combo_preset.findText("Gorras") == -1
    assert not editor.accion_borrar_preset.isEnabled()


def test_exportar_jpg_con_fondo_blanco(abierto, qtbot, tmp_path):
    from image_studio.core.export import ExportSettings, Fondo

    abierto.quitar_fondo()
    qtbot.waitUntil(lambda: not abierto.ocupado)
    destino = abierto.exportar_en(tmp_path / "salida", ExportSettings(formato="jpg", fondo=Fondo.BLANCO))
    assert destino.suffix == ".jpg"
    with Image.open(destino) as imagen:
        assert imagen.getpixel((0, 0)) == (255, 255, 255)
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/tools/test_editor.py -q
```
Esperado: `AttributeError: 'EditorTool' object has no attribute 'guardar_preset'`.
(`test_exportar_jpg_con_fondo_blanco` ya pasa porque `exportar_en` existe desde la tarea 8.)

**Paso 3 - Implementar** en `src/image_studio/tools/background_removal/editor.py`:

1. Agregar a los imports, después de `from image_studio.tools.base import Tool`:
   ```python
   from image_studio.pipeline.settings import PRESETS
   from image_studio.ui.export_dialog import ExportDialog
   from image_studio.ui.preset_dialog import PresetDialog
   ```
2. En `__init__`, después de `self.ocupado = False`, agregar:
   ```python
           self._exportacion = ExportSettings()
   ```
3. En `_crear_interfaz`, después de la línea que crea `self.accion_100`, agregar:
   ```python
           self.accion_exportar = self._accion("Exportar...", ["Ctrl+Shift+S"], lambda *_: self._exportar_dialogo())
           self.accion_guardar_preset = self._accion("Guardar preset...", [], lambda *_: self._guardar_preset_dialogo())
           self.accion_borrar_preset = self._accion("Borrar preset", [], lambda *_: self.borrar_preset(self.combo_preset.currentText()))
   ```
   y reemplazar `        self.recargar_presets("producto")` por:
   ```python
           self.combo_preset.currentTextChanged.connect(lambda *_: self._actualizar_presets())
           self.recargar_presets("producto")
   ```
   Reemplazar `        for accion in (self.accion_abrir, self.accion_pegar, self.accion_guardar):`
   por `        for accion in (self.accion_abrir, self.accion_pegar, self.accion_guardar, self.accion_exportar):`
   y, en la barra, después de `        barra.addAction(self.accion_quitar)`, agregar:
   ```python
           barra.addAction(self.accion_guardar_preset)
           barra.addAction(self.accion_borrar_preset)
   ```
4. Al final de `recargar_presets`, agregar:
   ```python
           self._actualizar_presets()
   ```
5. En `_actualizar_estado`, reemplazar
   `        for accion in (self.accion_guardar, self.accion_quitar, self.accion_antes, self.accion_ajustar, self.accion_100):`
   por
   `        for accion in (self.accion_guardar, self.accion_exportar, self.accion_quitar, self.accion_antes, self.accion_ajustar, self.accion_100):`.
6. Agregar estos métodos al final de la clase:
   ```python

    # Presets y exportación

    def _actualizar_presets(self) -> None:
        if hasattr(self, "accion_borrar_preset"):
            self.accion_borrar_preset.setEnabled(self.combo_preset.currentText() not in PRESETS)

    def guardar_preset(self, nombre: str, ajustes: PipelineSettings) -> None:
        nombre = self._presets.guardar(nombre, ajustes)
        self.recargar_presets(nombre)
        self.informar(f"Preset guardado: {nombre}")

    def borrar_preset(self, nombre: str) -> None:
        if nombre in PRESETS:
            return
        self._presets.borrar(nombre)
        self.recargar_presets("producto")
        self.informar(f"Preset borrado: {nombre}")

    def _guardar_preset_dialogo(self) -> None:
        dialogo = PresetDialog(self._ajustes_actuales(), set(PRESETS), self)
        if dialogo.exec():
            self.guardar_preset(*dialogo.valor())

    def _exportar_dialogo(self) -> None:
        if self.sesion is None:
            return
        dialogo = ExportDialog(self._exportacion, self)
        if not dialogo.exec():
            return
        self._exportacion = dialogo.ajustes()
        formato = self._exportacion.formato
        sugerido = str(self.sesion.doc.path.with_suffix("." + formato))
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar", sugerido, f"{formato.upper()} (*.{formato})")
        if ruta:
            self.exportar_en(Path(ruta), self._exportacion)
   ```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `13 passed`.

**Commit:**
```powershell
git add src/image_studio/tools/background_removal/editor.py tests/tools/test_editor.py
git commit -m "feat(tools): presets propios y exportacion completa en el editor"
```

### Tarea 11: herramienta de lotes

**Archivos:** crear `src/image_studio/tools/batch/__init__.py`,
`src/image_studio/tools/batch/panel.py`, `tests/tools/test_batch.py`

**Paso 1 - Tests que fallan:**
```python
import time

import pytest

from image_studio.core.export import ExportSettings
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.tools.batch.panel import BatchTool


class RemovedorLento:
    def __init__(self, base, espera=0.0):
        self.base = base
        self.espera = espera

    def run(self, doc, ajustes, usar_alfa_existente=False):
        time.sleep(self.espera)
        return self.base.run(doc, ajustes)


def _panel(qtbot, removedor):
    panel = BatchTool(RemoverCache(lambda modelo, dispositivo, progreso: removedor), PresetStore())
    qtbot.addWidget(panel)
    panel.show()
    return panel


@pytest.fixture
def carpetas(tmp_path, escribir_png):
    entrada = tmp_path / "entrada"
    for nombre in ("a.png", "b.png", "c.png"):
        escribir_png(entrada / nombre)
    (entrada / "roto.png").write_bytes(b"x")
    return entrada, tmp_path / "salida"


def test_procesa_la_carpeta_y_llena_la_tabla(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    assert panel.ocupado and not panel.boton_iniciar.isEnabled()
    qtbot.waitUntil(lambda: not panel.ocupado)
    assert panel.tabla.rowCount() == 4
    estados = [panel.tabla.item(fila, 1).text() for fila in range(4)]
    assert estados == ["ok", "ok", "ok", "error"]
    assert panel.barra.value() == 4
    assert (salida / "informe.csv").exists()
    assert "Lote terminado: 3 ok, 0 baja confianza, 1 con error" in panel.ultimo_mensaje


def test_doble_clic_pide_abrir_en_el_editor(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    qtbot.waitUntil(lambda: not panel.ocupado)
    with qtbot.waitSignal(panel.abrir_en_editor) as senal:
        panel._abrir_fila(panel.tabla.item(1, 0))
    assert senal.args == [entrada / "b.png"]


def test_carpeta_de_entrada_inexistente(qtbot, tmp_path, removedor_falso):
    panel = _panel(qtbot, removedor_falso)
    panel.edit_entrada.setText(str(tmp_path / "no"))
    panel.edit_salida.setText(str(tmp_path / "salida"))
    panel.iniciar()
    assert not panel.ocupado
    assert "no existe" in panel.ultimo_mensaje


def test_cancelar_detiene_el_lote(qtbot, tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    for i in range(20):
        escribir_png(entrada / f"{i:02d}.png")
    panel = _panel(qtbot, RemovedorLento(removedor_falso, espera=0.05))
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(tmp_path / "salida"))
    panel.iniciar()
    panel.cancelar()
    qtbot.waitUntil(lambda: not panel.ocupado, timeout=10000)
    assert panel.tabla.rowCount() < 20
    assert "cancelado" in panel.ultimo_mensaje


def test_usa_la_exportacion_elegida(qtbot, carpetas, removedor_falso):
    entrada, salida = carpetas
    panel = _panel(qtbot, removedor_falso)
    panel.set_exportacion(ExportSettings(formato="webp"))
    assert "webp" in panel.etiqueta_exportacion.text()
    panel.edit_entrada.setText(str(entrada))
    panel.edit_salida.setText(str(salida))
    panel.iniciar()
    qtbot.waitUntil(lambda: not panel.ocupado)
    assert (salida / "a.webp").exists()
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/tools/test_batch.py -q
```
Esperado: `ModuleNotFoundError: No module named 'image_studio.tools.batch'`.

**Paso 3 - Implementar.** Crear vacío `src/image_studio/tools/batch/__init__.py` y
`src/image_studio/tools/batch/panel.py`:
```python
"""Herramienta Lotes: quitar fondos de una carpeta con progreso, cancelación y tabla."""

from __future__ import annotations

import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_studio.core.export import ExportSettings
from image_studio.pipeline.batch import NOMBRE_INFORME, BatchItem, run_batch
from image_studio.pipeline.presets_store import PresetStore
from image_studio.pipeline.remover_cache import RemoverCache
from image_studio.tools.base import Tool
from image_studio.ui.export_dialog import ExportDialog
from image_studio.workers.tasks import ejecutar

COLUMNAS = ("Archivo", "Estado", "Tiempo (s)", "Motivo")


class BatchTool(Tool):
    id = "lotes"
    nombre = "Lotes"
    icono_estandar = QStyle.StandardPixmap.SP_FileDialogDetailedView
    abrir_en_editor = Signal(Path)

    def __init__(self, cache: RemoverCache, presets: PresetStore, parent=None):
        super().__init__(parent)
        self._cache = cache
        self._presets = presets
        self._exportacion = ExportSettings()
        self._cancelar = threading.Event()
        self._rutas: list[Path] = []
        self.ocupado = False

        self.edit_entrada = QLineEdit()
        self.edit_salida = QLineEdit()
        self.combo_preset = QComboBox()
        self.etiqueta_exportacion = QLabel()
        boton_exportacion = QPushButton("Exportación...")
        boton_exportacion.clicked.connect(self._elegir_exportacion)
        self.boton_iniciar = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Iniciar")
        self.boton_iniciar.clicked.connect(self.iniciar)
        self.boton_cancelar = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar)
        self.barra = QProgressBar()
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.itemDoubleClicked.connect(self._abrir_fila)

        formulario = QFormLayout()
        formulario.addRow("Entrada", self._con_boton(self.edit_entrada, "Carpeta de entrada"))
        formulario.addRow("Salida", self._con_boton(self.edit_salida, "Carpeta de salida"))
        formulario.addRow("Preset", self.combo_preset)
        fila_exportacion = QHBoxLayout()
        fila_exportacion.addWidget(self.etiqueta_exportacion, 1)
        fila_exportacion.addWidget(boton_exportacion)
        formulario.addRow("Exportación", fila_exportacion)
        botones = QHBoxLayout()
        botones.addWidget(self.boton_iniciar)
        botones.addWidget(self.boton_cancelar)
        botones.addWidget(self.barra, 1)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addLayout(botones)
        diseno.addWidget(self.tabla)

        self.recargar_presets()
        self.set_exportacion(self._exportacion)
        self._actualizar_estado()
        self.informar("Elige una carpeta de entrada y otra de salida")

    def _con_boton(self, campo: QLineEdit, titulo: str) -> QWidget:
        boton = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "")
        boton.clicked.connect(lambda: self._elegir_carpeta(campo, titulo))
        fila = QWidget()
        diseno = QHBoxLayout(fila)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(campo, 1)
        diseno.addWidget(boton)
        return fila

    def _elegir_carpeta(self, campo: QLineEdit, titulo: str) -> None:
        carpeta = QFileDialog.getExistingDirectory(self, titulo, campo.text())
        if carpeta:
            campo.setText(carpeta)

    def recargar_presets(self) -> None:
        actual = self.combo_preset.currentText() or "producto"
        self.combo_preset.clear()
        self.combo_preset.addItems(list(self._presets.todos()))
        self.combo_preset.setCurrentText(actual)

    def set_exportacion(self, ajustes: ExportSettings) -> None:
        self._exportacion = ajustes
        recorte = f", recorte {ajustes.margen_px} px" if ajustes.recortar else ""
        self.etiqueta_exportacion.setText(f"{ajustes.formato}, fondo {ajustes.fondo.value}{recorte}")

    def _elegir_exportacion(self) -> None:
        dialogo = ExportDialog(self._exportacion, self)
        if dialogo.exec():
            self.set_exportacion(dialogo.ajustes())

    def _actualizar_estado(self) -> None:
        self.boton_iniciar.setEnabled(not self.ocupado)
        self.boton_cancelar.setEnabled(self.ocupado)

    def iniciar(self) -> None:
        if self.ocupado:
            return
        entrada = Path(self.edit_entrada.text().strip())
        salida = Path(self.edit_salida.text().strip())
        if not self.edit_entrada.text().strip() or not entrada.is_dir():
            self.informar(f"La carpeta de entrada no existe: {entrada}")
            return
        if not self.edit_salida.text().strip():
            self.informar("Elige una carpeta de salida")
            return
        self.recargar_presets()
        ajustes = self._presets.todos()[self.combo_preset.currentText()]
        self._cancelar = threading.Event()
        self._rutas = []
        self.tabla.setRowCount(0)
        self.barra.setValue(0)
        self.ocupado = True
        self._actualizar_estado()
        self.informar(f"Procesando {entrada.name} con el preset {self.combo_preset.currentText()}...")
        ejecutar(
            self._correr,
            entrada,
            salida,
            ajustes,
            self._exportacion,
            self._cancelar,
            al_avanzar=self._avance,
            al_terminar=lambda items: self._terminado(items, salida),
            al_fallar=self._fallido,
        )

    def _correr(self, entrada, salida, ajustes, exportar, cancelar, reportar):
        # Corre en un hilo de trabajo; el modelo se carga una vez y lo comparte el editor.
        removedor = self._cache.get(ajustes.modelo)
        return run_batch(
            entrada,
            salida,
            removedor,
            ajustes,
            exportar,
            progreso=lambda hechos, total, item: reportar((hechos, total, item)),
            cancelar=cancelar,
        )

    def _avance(self, dato) -> None:
        hechos, total, item = dato
        self.barra.setMaximum(total)
        self.barra.setValue(hechos)
        self._agregar_fila(item)

    def _agregar_fila(self, item: BatchItem) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        for columna, texto in enumerate((item.archivo.name, item.estado, f"{item.tiempo_s:.2f}", item.motivo)):
            self.tabla.setItem(fila, columna, QTableWidgetItem(texto))
        self._rutas.append(item.archivo)

    def _abrir_fila(self, celda: QTableWidgetItem) -> None:
        self.abrir_en_editor.emit(self._rutas[celda.row()])

    def _terminado(self, items: list[BatchItem], salida: Path) -> None:
        self.ocupado = False
        self._actualizar_estado()
        conteo = Counter(item.estado for item in items)
        inicio = "Lote cancelado" if self._cancelar.is_set() else "Lote terminado"
        self.informar(
            f"{inicio}: {conteo['ok']} ok, {conteo['baja_confianza']} baja confianza, "
            f"{conteo['error']} con error. Informe: {salida / NOMBRE_INFORME}"
        )

    def _fallido(self, mensaje: str) -> None:
        self.ocupado = False
        self._actualizar_estado()
        self.informar(f"Error: {mensaje}")

    def cancelar(self) -> None:
        self._cancelar.set()

    def detener(self) -> None:
        self.cancelar()
```

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `5 passed`.

**Commit:**
```powershell
git add src/image_studio/tools/batch tests/tools/test_batch.py
git commit -m "feat(tools): agregar herramienta de lotes con progreso y cancelacion"
```

### Tarea 12: conectar Lotes con el editor

**Archivos:** modificar `src/image_studio/ui/app.py`, `tests/ui/test_app.py`, `README.md`

**Paso 1 - Test que falla.** Agregar al final de `tests/ui/test_app.py`:
```python


def test_lotes_abre_la_imagen_en_el_editor(qtbot, escribir_png, tmp_path):
    ventana = crear_ventana([])
    qtbot.addWidget(ventana)
    assert [ventana.lista.item(i).text() for i in range(ventana.lista.count())] == ["Quitar fondo", "Lotes"]
    ventana.mostrar("lotes").abrir_en_editor.emit(escribir_png(tmp_path / "b.png"))
    assert ventana.actual().id == "editor"
    assert ventana.herramienta("editor").sesion.doc.path.name == "b.png"
```

**Paso 2 - Verificar que falla:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ui/test_app.py -q
```
Esperado: `StopIteration` al pedir la herramienta `lotes`.

**Paso 3 - Implementar** en `src/image_studio/ui/app.py`:

1. Después de `from image_studio.tools.base import Tool` agregar
   `from image_studio.tools.batch.panel import BatchTool`.
2. En `crear_herramientas`, reemplazar `    return [EditorTool(cache, presets)]` por
   `    return [EditorTool(cache, presets), BatchTool(cache, presets)]`.
3. En `crear_ventana`, después de `    ventana = MainWindow(herramientas)` agregar:
   ```python
       editor, lotes = ventana.herramienta("editor"), ventana.herramienta("lotes")
       lotes.abrir_en_editor.connect(lambda ruta: (ventana.mostrar("editor"), editor.abrir(ruta)))
       # Los presets creados en una herramienta aparecen en la otra al cambiar de panel.
       ventana.lista.currentRowChanged.connect(lambda *_: (editor.recargar_presets(), lotes.recargar_presets()))
   ```

Agregar al final de `README.md`:
````markdown

## Uso (Hito 3: suite)

La barra lateral cambia entre **Quitar fondo** (editor) y **Lotes**. En Lotes se eligen las
carpetas, el preset y la exportación; doble clic en una fila abre esa imagen en el editor para
retocarla. Los presets propios se guardan en `%APPDATA%\ImageStudio\presets.json`.
````

**Paso 4 - Verificar que pasa:** mismo comando. Esperado: `4 passed`.

**Commit:**
```powershell
git add src/image_studio/ui/app.py tests/ui/test_app.py README.md
git commit -m "feat(ui): agregar lotes a la suite y abrir resultados en el editor"
```

---

## Fase D - Verificación

### Tarea 13: cierre del hito

Sin archivos nuevos.

**Paso 1 - Suite completa:**
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```
Esperado: todo `passed`; `skipped` solo en `tests/golden`. `$LASTEXITCODE` igual a 0.

**Paso 2 - Prueba con la app real** (no offscreen), automatizada con un script en el
scratchpad que use `crear_ventana`, como en el Hito 2, y capturas de pantalla de cada paso:

1. Crear un preset propio desde el editor y verlo en Lotes.
2. Lote de 5 imágenes con el preset persona y exportación WebP con recorte: la tabla se llena
   mientras avanza y la ventana responde.
3. Cancelar un lote de 20 imágenes a mitad de camino.
4. Doble clic en una fila: la imagen se abre en el editor.
5. Exportar desde el editor a JPG con fondo de color.

**Paso 3 - PR a develop:**
```powershell
git push -u origin feature/hito-3-suite
gh pr create --base develop --title "feat(tools): suite con lotes, presets propios y exportacion (hito 3)"
```
El cuerpo incluye qué cambia, por qué, archivos, resultado de la suite, la decisión sobre
ViTMatte y el resultado de la prueba con la app real. Integración por squash.

---

## Cobertura de la spec en este hito

| Requisito | Tarea |
|---|---|
| Interfaz `Tool`; una herramienta nueva no modifica `core` ni las demás | 7, 8, 9 |
| Lote desde la interfaz con progreso y cancelación | 4, 11 |
| Abrir imágenes del lote en el editor | 11, 12 |
| Presets propios guardados | 2, 6, 10 |
| Exportación PNG/WebP/JPG, fondo, color, recorte, margen, DPI desde la interfaz | 5, 10, 11 |
| Un solo modelo cargado para editor y lotes | 3 |
| Riesgo R1 (ViTMatte) | 1 (decidido: no se adopta) |
