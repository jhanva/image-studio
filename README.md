<div align="center">

# Image Studio

Suite de escritorio para Windows que prepara imágenes para catálogo, sublimación y DTF: quita
fondos con IA y convierte diseños a semitonos listos para imprimir, una imagen a la vez.

**Dos herramientas, una sola app. Todo se procesa en tu equipo, sin servicios externos.**

[![Versión](https://img.shields.io/badge/versi%C3%B3n-0.5.0-0ea5e9?style=for-the-badge)](CHANGELOG.md)
[![Herramientas](https://img.shields.io/badge/herramientas-2-84cc16?style=for-the-badge)](#herramientas)
[![Python](https://img.shields.io/badge/python-3.14-8b5cf6?style=for-the-badge)](#desde-el-c%C3%B3digo-fuente)
[![Windows](https://img.shields.io/badge/windows-10%20%7C%2011-f97316?style=for-the-badge)](#requisitos)

[Inicio rápido](#inicio-rápido) • [Herramientas](#herramientas) • [Instalación](#instalación) • [Uso](#uso) • [Modelos](#modelos) • [Contribuir](#contribuir)

</div>

## Inicio rápido

Con el instalador:

1. Ejecutar `ImageStudio-Setup-X.Y.Z.exe`. Instala para el usuario actual, sin permisos de
   administrador.
2. Abrir **Image Studio** desde el menú Inicio.
3. Arrastrar una foto a la ventana y pulsar **Quitar fondo** (Ctrl+R).

Desde el código fuente:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio
```

La primera vez que se quita un fondo se descarga el modelo de IA (entre 180 MB y 1 GB, según el
equipo) y se guarda para los siguientes usos.

## Índice

- [Cómo funciona](#cómo-funciona)
- [Herramientas](#herramientas)
- [Instalación](#instalación)
  - [Requisitos](#requisitos)
  - [Instalador](#instalador)
  - [Desde el código fuente](#desde-el-código-fuente)
  - [Actualizar y desinstalar](#actualizar-y-desinstalar)
- [Uso](#uso)
  - [Quitar fondo](#quitar-fondo)
  - [Semitonos](#semitonos)
  - [Línea de comandos](#línea-de-comandos)
- [Modelos](#modelos)
- [Rendimiento](#rendimiento)
- [Datos del usuario](#datos-del-usuario)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Contribuir](#contribuir)
- [Solución de problemas](#solución-de-problemas)
- [Estado y hoja de ruta](#estado-y-hoja-de-ruta)
- [Principios](#principios)
- [Licencia](#licencia)

## Cómo funciona

La app es un solo proceso en Python con interfaz PySide6 (Qt). El código se reparte en capas con
fronteras estrictas:

| Capa | Qué hace | Dónde vive |
|---|---|---|
| **Núcleo** | Carga y guarda imágenes, operaciones de máscara, pinceles, historial, semitonos | `src/image_studio/core/` |
| **Motores** | Inferencia de IA con ONNX Runtime (CUDA con respaldo a CPU), matting, gestión de modelos | `src/image_studio/engines/` |
| **Pipeline** | Une núcleo y motores: quitar fondo, sesiones de edición, presets | `src/image_studio/pipeline/` |
| **Herramientas** | Cada panel de la suite implementa la interfaz `Tool` | `src/image_studio/tools/` |
| **Interfaz** | Ventana, lienzo, diálogos y tareas en segundo plano | `src/image_studio/ui/`, `src/image_studio/workers/` |

- `core`, `engines` y `pipeline` no importan Qt; un test lo comprueba. Todo lo que procesa
  imágenes se puede probar sin abrir ventanas.
- Agregar una herramienta nueva no modifica las demás: se implementa `Tool` y se registra en
  `ui/app.py`.
- Al arrancar, la app detecta el equipo y elige modelo y dispositivo: GPU NVIDIA con 8 GB o más
  usa BiRefNet en GPU; el resto, BiRefNet liviano en CPU. Si la GPU falla, sigue en CPU y lo
  avisa en la barra de estado.

## Herramientas

| Herramienta | Para qué | Qué incluye | Estado |
|---|---|---|---|
| **Quitar fondo** | Fotos de producto e imágenes para sublimar (personas, mascotas, logos) | Segmentación con IA, matting de bordes, limpieza de color, pinceles Conservar, Borrar y Refinar borde, deshacer, presets y exportación PNG, WebP o JPG | Publicada (0.3.0) |
| **Semitonos** | Diseños para DTF y sublimación sobre camisetas | Knockout del color de la camiseta, degradado con siete patrones de trama, limpieza de fondo, borradores, presets, vista previa en vivo y PNG con alfa binario a 300 DPI | Publicada (0.5.0) |

## Instalación

### Requisitos

| Recurso | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 u 11 de 64 bits | Windows 11 |
| Memoria | 8 GB de RAM | 16 GB |
| Disco | 4 GB libres (2.3 GB la app y hasta 1.3 GB los modelos) | SSD |
| GPU | No necesaria | NVIDIA con 8 GB de VRAM |

Las GPU AMD e Intel no se aprovechan: la app usa la CPU en esos equipos.

### Instalador

`ImageStudio-Setup-X.Y.Z.exe` instala en `%LOCALAPPDATA%\Programs\Image Studio`, crea accesos
directos y un desinstalador, y prepara el motor de recorte durante la instalación (hasta un
minuto). El ejecutable no está firmado, así que Windows SmartScreen puede pedir confirmación
(ver [Solución de problemas](#solución-de-problemas)).

Construir el instalador (requiere [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
.\scripts\build.ps1
```

Solo el ejecutable, sin instalador, en `dist\ImageStudio\`:

```powershell
.\scripts\build.ps1 -SinInstalador
```

### Desde el código fuente

Todo Python y pip se ejecutan desde el `.venv` de la raíz del repo (Python 3.14):

```powershell
py -3.14 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio
```

`requirements.txt` tiene las dependencias de la app; `requirements-dev.txt` agrega las de
pruebas y exportación de modelos.

### Actualizar y desinstalar

- **Actualizar**: ejecutar el instalador de la versión nueva encima de la anterior. Reemplaza los
  archivos internos y conserva presets y modelos.
- **Desinstalar**: Configuración de Windows > Aplicaciones > Image Studio. Los presets
  (`%APPDATA%\ImageStudio`) y los modelos (`%LOCALAPPDATA%\ImageStudio\models`) quedan en el
  equipo; se pueden borrar a mano.

## Uso

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio D:\fotos\termo.jpg
```

Abrir la app con una ruta carga esa imagen en **Quitar fondo**. La barra lateral cambia de
herramienta.

### Quitar fondo

Abrir (Ctrl+O), arrastrar o pegar (Ctrl+V) una imagen, elegir el preset y pulsar **Quitar
fondo**. Los pinceles corrigen el resultado sobre la máscara a resolución completa: lo que se ve
en el lienzo es lo que se exporta.

| Preset | Para qué |
|---|---|
| **producto** | Termos, pocillos y objetos con borde nítido; sin matting para que brillos y vidrio no queden semitransparentes, con limpieza de color |
| **persona** | Personas y mascotas: pelo, pelaje y bordes semitransparentes; con matting y limpieza de color |

| Atajo | Acción | Atajo | Acción |
|---|---|---|---|
| Ctrl+O | Abrir | V | Mover |
| Ctrl+V | Pegar | K | Pincel Conservar |
| Ctrl+R | Quitar fondo | E | Pincel Borrar |
| Ctrl+S | Guardar PNG | R | Pincel Refinar borde |
| Ctrl+Shift+S | Exportar con opciones | B | Ver original |
| Ctrl+Z / Ctrl+Y | Deshacer / rehacer | Ctrl+0 / Ctrl+1 | Ajustar / 100% |

Rueda del ratón: zoom. Botón central: desplazar.

### Semitonos

Prepara diseños para DTF o sublimación: elimina el color de la camiseta y convierte en puntos de
semitono los colores cercanos a él, para un tacto más suave y menos tinta. Es independiente de
Quitar fondo: para usar un recorte, primero se exporta como PNG y luego se abre aquí.

Se abre un diseño, se mueven los controles mirando la vista previa (se recalcula en segundo plano
mientras se ajusta) y se exporta.

| Grupo | Controles |
|---|---|
| **Color a eliminar** | Negro, blanco, automático o tomado del arte con el cuentagotas |
| **Limpieza** | Quitar el fondo sólido, quitarlo también dentro del arte, colores a borrar, tolerancia y encoger borde |
| **Trama** | Frecuencia (LPI), ángulo, ajuste a la rejilla (sin moiré) y patrón: redondo, diamante, elipse, cuadrado, línea, líneas onduladas o puntos ondulados |
| **Degradado** | Alcance, peso del punto, descartar puntos pequeños, semitransparencias, bordes limpios y restaurar color de tinta |
| **Impresión** | Ancho en pulgadas a 300 DPI (máximo 60 MP) |
| **Borradores** | Borrar (E), Proteger sin semitono (P) y Quitar marca (Q); `[` y `]` cambian el tamaño |

T alterna la vista sobre la camiseta o sobre transparencia; B muestra el original; Ctrl+Shift+S
exporta un PNG RGBA con alfa binario (solo 0 o 255), como exige el film DTF.

### Línea de comandos

`image-studio-cli.exe` en la instalación, o `python -m image_studio` desde el código. Solo trae
comandos de mantenimiento; el trabajo con imágenes se hace en la app, una imagen a la vez.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio diagnostico
```

| Comando | Qué hace |
|---|---|
| `diagnostico` | Muestra el equipo detectado, la elección automática y prueba el motor |
| `preparar` | Compila el motor de matting (lo usa el instalador) |

## Modelos

Los modelos no se versionan en el repo. `engines/model_manager.py` los descarga al primer uso,
verifica su SHA-256 y los guarda en `%LOCALAPPDATA%\ImageStudio\models`.

| Modelo | Uso | Tamaño | Licencia |
|---|---|---|---|
| BiRefNet general | Calidad, en GPU NVIDIA de 8 GB o más | 928 MB | MIT |
| BiRefNet liviano (Swin tiny) | Equipos sin GPU suficiente, en CPU | 214 MB | MIT |
| ISNet general-use | Modo rápido para previews y equipos lentos | 170 MB | Apache-2.0 |
| Matting clásico (pymatting) | Bordes de pelo y semitransparencias | Sin descarga | MIT |

ViTMatte se evaluó y no se adopta: sus pesos públicos se entrenaron con un dataset de uso no
comercial. Semitonos no usa IA.

## Rendimiento

Medido en el equipo de referencia (RTX 3050 de 8 GB, Core i5-10400, 16 GB de RAM):

| Operación | Tiempo |
|---|---|
| Quitar fondo, BiRefNet en GPU | unos 5 s por foto |
| Quitar fondo, BiRefNet liviano en CPU | unos 13 a 15 s por foto |
| Semitonos, diseño de 3600x4800, cambio de control hasta la imagen completa | 0.9 a 1.3 s |
| Semitonos, zona visible al 100% | 0.19 s |

`scripts/benchmark.py` mide el quitafondos y `scripts/bench_halftone.py` las etapas del semitono.
En equipos con menos núcleos los tiempos de CPU suben.

## Datos del usuario

| Qué | Dónde |
|---|---|
| Presets de Quitar fondo | `%APPDATA%\ImageStudio\presets.json` |
| Presets de Semitonos | `%APPDATA%\ImageStudio\halftone_presets.json` |
| Modelos descargados | `%LOCALAPPDATA%\ImageStudio\models` |
| App instalada | `%LOCALAPPDATA%\Programs\Image Studio` |

## Estructura del repositorio

```
src/image_studio/
  core/                   Python puro: E/S de imagen, máscara, pinceles, historial, exportación
    halftone/             trama por umbral, knockout, limpieza y etapas del semitono
  engines/                ONNX Runtime, segmentadores, matting, modelos, detección del equipo
  pipeline/               quitar fondo, sesiones, presets, caché de removedores
  tools/                  herramientas de la suite (interfaz Tool)
    background_removal/   Quitar fondo
    halftone/             Semitonos
  ui/                     ventana, lienzo, diálogos y tema
  workers/                tareas en segundo plano
  cli.py                  línea de comandos de mantenimiento
tests/                    pruebas por capa; tests/golden para el set de calidad privado
scripts/                  build.ps1, benchmark.py, bench_halftone.py
packaging/                PyInstaller (image_studio.spec), Inno Setup (instalador.iss), lanzador
docs/
  spec.md                 diseño del MVP de quitar fondos
  spec-semitonos.md       diseño de la herramienta Semitonos
  plans/                  planes de implementación por hito
  repo-workflow.md        gitflow, commits, PR y versiones
AGENTS.md                 reglas de trabajo para agentes
CHANGELOG.md              cambios por versión
```

## Contribuir

Las reglas completas están en [AGENTS.md](AGENTS.md) y el flujo en
[docs/repo-workflow.md](docs/repo-workflow.md). Resumen operativo:

### Agregar una herramienta

1. Escribir su spec en `docs/` y su plan en `docs/plans/`.
2. Poner la lógica sin Qt en `core/` o `pipeline/`, con pruebas.
3. Crear el panel en `tools/<herramienta>/` como subclase de `Tool` (`id`, `nombre`, icono y
   mensajes de estado).
4. Registrarla en `crear_herramientas` de `ui/app.py`.
5. Documentarla en este README y en `CHANGELOG.md`.

### Verificar antes de abrir PR

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```

Las pruebas usan imágenes sintéticas. El golden set con fotos reales vive fuera del repo; para
correrlo, definir `IMAGE_STUDIO_GOLDEN_DIR`. Si un cambio toca `engines/`, `pipeline/` o modelos,
el golden set no debe empeorar.

### Flujo git

Gitflow con `main` (publicado) y `develop` (integración). Ramas `feature/`, `fix/` o `agent/`
desde `develop`; PR con squash hacia `develop`; publicación con merge commit `develop` a `main` y
etiqueta `vX.Y.Z`. Commits en Conventional Commits, en español, sin atribución de asistentes. La
versión vive solo en `pyproject.toml`.

### Reglas del repositorio público

- Nunca versionar fotos de clientes, personas reales ni imágenes sin licencia libre.
- No mencionar nombres de clientes ni de negocios en código, documentación ni commits.
- Sin emojis en código, comentarios, commits ni textos de la interfaz.

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Windows SmartScreen bloquea el instalador | El ejecutable no está firmado | "Más información" > "Ejecutar de todas formas" |
| La primera vez que se quita un fondo tarda mucho | Se está descargando el modelo | Esperar la descarga; la app no muestra el avance. Requiere internet solo esa vez |
| Hay GPU NVIDIA pero la app usa CPU | VRAM insuficiente o driver sin CUDA | `image-studio-cli.exe diagnostico` muestra el equipo detectado y el motivo |
| Quitar fondo es lento | Equipo sin GPU NVIDIA de 8 GB | Usar el modelo rápido (ISNet) |
| Semitonos muestra patrones raros con la imagen reducida | Moiré de pantalla al ajustar a la ventana | Revisar al 100% (Ctrl+1); la exportación es a resolución completa |
| Semitonos limita el ancho de impresión | La imagen superaría 60 MP | Reducir el ancho; a 300 DPI equivale a unas 20x30 pulgadas |
| El resultado de Semitonos no tiene tinta | El color a eliminar coincide con todo el arte | Revisar el color a eliminar; la exportación avisa antes de guardar |

## Estado y hoja de ruta

| Versión | Contenido |
|---|---|
| 0.3.0 | Quitar fondo, editor con pinceles, lotes, presets propios y exportación |
| 0.4.0 | Instalador único que se adapta al equipo, CLI `diagnostico` y `preparar` |
| 0.5.0 | Semitonos para DTF y sublimación |
| 0.6.0 | Se retiran los lotes: todas las herramientas trabajan una imagen a la vez |

Pendiente:

- Probar el instalador en un Windows sin Python ni GPU NVIDIA.
- Instalador más liviano para equipos sin GPU NVIDIA (hoy incluye CUDA en todos los casos).
- Licencias y avisos de terceros antes de distribuir a otras personas.

Detalle por versión en [CHANGELOG.md](CHANGELOG.md).

## Principios

1. **Calidad del resultado primero**: por encima de la estética de la interfaz y del tiempo de
   desarrollo.
2. **Todo local**: ninguna imagen sale del equipo.
3. **Lo que se ve es lo que se exporta**: el lienzo trabaja a resolución completa.
4. **No inventar**: modelos, pesos, licencias y hashes se comprueban antes de usarlos.
5. **Medir antes de afirmar**: tiempos y calidad con scripts y golden set, no a ojo.
6. **Una imagen a la vez**: cada herramienta abre, ajusta y exporta una sola imagen; no hay
   procesamiento por lotes.

## Licencia

Uso personal.
