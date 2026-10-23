# Image Studio - Spec del MVP: Quitar fondos

Estado: borrador para aprobación
Fecha: 2026-10-22
Autor: Johan (jhanva)

## 1. Problema y contexto

El uso principal es un negocio de productos sublimables (termos, pocillos, camisetas) que
necesita recortar fondos de dos tipos de imágenes con la misma frecuencia:

- **Fotos de producto** para catálogo y redes: bordes limpios y nítidos, procesamiento por lotes,
  exportación con fondo transparente o blanco.
- **Imágenes de clientes para sublimar** (personas, mascotas, logos): pelo, pelaje y bordes
  semitransparentes, con corrección manual cuando el modelo falla.

Se construye **Image Studio**, una aplicación de escritorio Windows de uso personal (un solo
usuario), concebida como una **suite de herramientas de imagen**. La primera
herramienta es quitar fondos con calidad profesional, procesando todo en local, sin servicios
externos.

Prioridad declarada: **calidad del resultado final** por encima de la estética de la interfaz y
del tiempo de desarrollo.

### Equipo objetivo

- GPU NVIDIA GeForce RTX 3050, CPU Intel Core i5-10400 (6 núcleos), 16 GB de RAM, Windows 10 Pro.
- La app debe funcionar también sin GPU (más lento).

## 2. Enfoque elegido y justificación

**PySide6 (Qt) con todo el código en Python**, en un solo proceso.

Se evaluaron tres enfoques (puntaje ponderado, prioridad en calidad):

| Enfoque | Puntaje | Motivo principal |
|---|---|---|
| A. PySide6 (Qt) | 9.0 | Editor nativo a resolución completa; un solo lenguaje que el mantenedor domina |
| B. Python (FastAPI) + front web en pywebview/Tauri | 7.8 | UI más moderna, pero edición de máscara en navegador suele hacerse sobre previews reducidos y suma un segundo stack |
| C. Flet / NiceGUI | 6.1 | Arranque rápido, pero lienzo insuficiente para retoque preciso |

La calidad del recorte automático es idéntica en los tres (mismos modelos). La diferencia está en
la precisión del retoque manual, que en A ocurre directamente sobre la máscara a resolución
completa: lo que se ve en el lienzo es lo que se exporta.

## 3. Diseño detallado

### 3.1 Stack

| Pieza | Elección |
|---|---|
| Lenguaje | Python 3.14 |
| UI | PySide6-Essentials + estilo Fusion con paleta oscura propia |
| Inferencia | ONNX Runtime: `onnxruntime-gpu[cuda,cudnn]` (CUDA) con respaldo a CPU; sesiones con `enable_mem_pattern = False` (con el patrón de memoria BiRefNet desborda 8 GB de VRAM y pasa de 1.5 s a 22 s) |
| Imagen | numpy, opencv-python-headless, Pillow, pillow-heif |
| Limpieza de color y matting clásico | pymatting |
| Pruebas | pytest, pytest-qt |
| Exportación de modelos (solo desarrollo) | PyTorch en un script aparte, no es dependencia de la app |

PyTorch no se incluye en la app: ONNX Runtime pesa cientos de MB frente a varios GB.

### 3.2 Modelos

| Rol | Modelo | Licencia | Uso |
|---|---|---|---|
| Segmentación calidad (por defecto) | BiRefNet (general), ONNX, entrada 1024x1024 | MIT | Todas las imágenes |
| Segmentación rápida | ISNet general-use, ONNX | Apache-2.0 | Previews y lotes grandes cuando se elija el modo rápido |
| Matting de borde | ViTMatte (small), exportado a ONNX | Ver riesgo R1 | Pelo, pelaje, semitransparencias. Se integra cuando se resuelva R1; mientras tanto se usa el matting clásico |
| Matting de respaldo | Matting clásico de pymatting (closed-form / learning-based) | MIT | Si ViTMatte no se adopta o falla |

Los modelos no se versionan en el repo. `model_manager` los descarga a
`%LOCALAPPDATA%\ImageStudio\models\`, verifica su SHA-256 y los cachea.

### 3.3 Estructura de datos

| Modelo | Contenido |
|---|---|
| `ImageDoc` | Imagen RGB `uint8` a resolución completa, alfa original si existía, ruta, DPI, perfil de color |
| `Mask` | Alfa `float32` en [0, 1], HxW a resolución completa. Fuente de verdad del recorte |
| `Trimap` | `uint8` HxW: 0 = fondo seguro, 128 = desconocido, 255 = frente seguro |
| `History` | Pila deshacer/rehacer con parches de máscara por tiles de 256x256; límite de 50 pasos o 1 GB |
| `PipelineSettings` | modelo, matting (sí/no), limpieza de color (sí/no), ancho de franja del trimap, suavizado y desplazamiento de borde |
| `Preset` | `PipelineSettings` con nombre. Incluidos: **Producto** (matting desactivado, borde nítido) y **Persona/mascota** (matting activado) |
| `ExportSettings` | formato (PNG, WebP, JPG), fondo (transparente, blanco, color), recorte al contenido (sí/no), margen en px, DPI |

### 3.4 Componentes

```
image-studio/
  src/image_studio/
    core/                 # Python puro, sin Qt
      image_io.py         # carga/normalización (EXIF, CMYK, 16-bit, HEIC) y guardado
      mask_ops.py         # suavizado, desplazamiento, umbral, recorte al contenido
      brush.py            # huella y estampado de pinceles
      history.py          # deshacer/rehacer por tiles
      export.py           # composición con fondo y escritura del archivo
      metrics.py          # IoU, SAD y MSE para el golden set
    engines/              # IA, sin Qt
      base.py             # interfaces Segmenter y Matter
      onnx_segmenter.py   # base común: preproceso, inferencia y escalado
      segment_birefnet.py
      segment_isnet.py
      matting_vitmatte.py
      matting_classic.py  # pymatting
      decontaminate.py    # estimación del color del frente en bordes
      model_manager.py    # descarga, hash, caché, selección de proveedor CUDA > CPU
    pipeline/             # sin Qt
      settings.py         # PipelineSettings y presets
      factory.py          # construye el removedor desde los modelos
      session.py          # sesión de edición: máscara, historial, pinceles, exportar
      refine_region.py    # matting solo sobre la zona pintada con Refinar borde
      remove_bg.py        # segmentar -> trimap -> matting -> limpieza de color
      batch.py            # lote sin interfaz + informe
    tools/
      base.py             # interfaz Tool: id, nombre, icono, panel, acciones
      background_removal/ # herramienta 1: panel de ajustes, presets, pinceles
    ui/                   # PySide6
      app.py              # arranque y tema
      main_window.py      # acciones, barra de herramientas y estado
      qt_image.py         # buffers numpy que respaldan QImage sin copia
      canvas/             # QGraphicsView: capa de imagen, tablero, zoom, trazos
      batch_panel.py      # Hito 3
      export_dialog.py    # Hito 3
    workers/              # QThreadPool: tareas en segundo plano con señales
    cli.py                # `python -m image_studio batch ...`
  scripts/
    export_models.py      # convierte pesos a ONNX (solo desarrollo, usa PyTorch)
  tests/
    fixtures/             # imágenes sintéticas o con licencia libre (versionadas)
    golden/               # runner de calidad; las imágenes privadas no se versionan
  docs/spec.md
```

El repositorio es público. El golden set con fotos reales (productos y clientes) vive fuera del
repo, en la carpeta indicada por la variable de entorno `IMAGE_STUDIO_GOLDEN_DIR`. Si la
variable no existe, las pruebas de calidad se omiten con un aviso; el resto de la suite corre
con `tests/fixtures/`.

Regla de fronteras: `core`, `engines` y `pipeline` no importan PySide6. Un test lo verifica.

Cada herramienta de la suite implementa `Tool` y se registra en `main_window`. Agregar una
herramienta nueva no requiere modificar `core` ni las demás herramientas.

### 3.5 Flujo de datos

Una imagen:

1. **Cargar**: aplicar orientación EXIF, convertir a RGB 8-bit, conservar el alfa original si existe.
2. **Segmentar**: BiRefNet a 1024x1024 y máscara escalada a la resolución original.
3. **Trimap**: franja de incertidumbre alrededor del borde (ancho configurable) marcada como desconocido.
4. **Matting** (si el preset lo activa): a resolución completa, solo sobre la franja desconocida,
   en recortes alrededor del sujeto para no exceder la VRAM.
5. **Limpieza de color** (si el preset lo activa): estimar el color del frente en píxeles de borde.
6. **Mostrar** en el lienzo con vista de tablero y comparación antes/después.
7. **Retocar**:
   - **Conservar / Borrar**: pincel con tamaño y dureza, escribe directo en `Mask`, registra parche en `History`.
   - **Refinar borde**: marca la región pintada como desconocido en `Trimap` y re-ejecuta el matting solo en esa región.
8. **Exportar** según `ExportSettings`.

Lote:

1. Elegir carpeta de entrada, carpeta de salida, preset y `ExportSettings`.
2. Procesar en segundo plano con barra de progreso y cancelación.
3. Generar `informe.csv` con archivo, estado (ok, error, baja confianza), tiempo y motivo.
4. Las imágenes de baja confianza se pueden abrir una por una en el editor.

**Baja confianza**: más del 15% de los píxeles de la máscara gruesa con alfa entre 0.1 y 0.9, o
sujeto que ocupa menos del 2% o más del 98% de la imagen.

### 3.6 Casos límite

| Caso | Manejo |
|---|---|
| Termos y pocillos con brillo o vidrio | Preset Producto: matting desactivado para que los reflejos no queden semitransparentes |
| Producto blanco sobre fondo blanco | Se marca baja confianza; se corrige con pincel Refinar borde |
| Imagen mayor a 8000 px por lado | Matting por tiles; el lienzo dibuja solo la zona visible (medido: 8 ms por cuadro a 10000x8000), sin pirámide |
| La imagen ya trae alfa | Se ofrece usar ese alfa como máscara inicial en lugar de segmentar |
| Sin GPU o sin VRAM suficiente | Reintento con tiles más pequeños; si vuelve a fallar, CPU, con aviso en la barra de estado |
| Modelo no descargado | La app abre igual; descarga con progreso y verificación de hash al primer uso |
| Archivo corrupto o formato no soportado | Mensaje claro; en lote se registra en el informe y se continúa |
| Varios sujetos y se quiere solo uno | Se resuelve con el pincel Borrar (selección por clic queda fuera del MVP) |

### 3.7 Entorno y convenciones

- Python y pip siempre desde `.venv` en la raíz del repo (`.\.venv\Scripts\python.exe -X utf8`).
- Dependencias en `requirements.txt` (app) y `requirements-dev.txt` (pruebas y exportación de modelos).
- Archivos de texto en UTF-8 sin BOM.
- Sin emojis en código, comentarios, mensajes de commit ni textos de la UI.
- La app se lanza con `python -m image_studio`. No hay instalador en el MVP.
- Ramas, commits, PR y versiones siguen [repo-workflow.md](repo-workflow.md) (Gitflow con
  `main` y `develop`, Conventional Commits en español, versión SemVer en `pyproject.toml`).
- Entregas por hitos: Hito 1 motor y CLI; Hito 2 editor (incluye guardar PNG transparente); Hito 3 suite (lotes en UI, presets propios, exportación en UI). Planes en `docs/plans/`.

## 4. Decisiones explícitas

### Incluido en el MVP

- Abrir una imagen (arrastrar y soltar, diálogo, pegar desde portapapeles).
- Formatos de entrada: JPG, PNG, WebP, BMP, TIFF, HEIC.
- Segmentación BiRefNet (calidad) e ISNet (rápido).
- Matting de borde y limpieza de color, activables por preset.
- Presets Producto y Persona/mascota, más presets propios guardados.
- Lienzo con zoom, desplazamiento, tablero de transparencia y antes/después.
- Pinceles Conservar, Borrar y Refinar borde; deshacer/rehacer.
- Procesamiento por lotes desde la UI y desde la línea de comandos, con informe CSV.
- Exportación PNG, WebP y JPG con fondo transparente, blanco o color; recorte al contenido con margen; DPI.
- Arquitectura de suite (`Tool`) lista para nuevas herramientas.

### Excluido del MVP

- Capas, texto, formas o composición de diseños.
- Mockups de productos, upscaling, vectorizado.
- Selección de sujeto por clic (SAM) o por texto.
- Instalador `.exe`, auto-actualización, sistema de licencias.
- Uso multiusuario, nube o API remota.
- Soporte DirectML para GPU AMD/Intel (el equipo objetivo es NVIDIA).

## 5. Riesgos

| Id | Riesgo | Mitigación |
|---|---|---|
| R1 | Los pesos de ViTMatte se entrenan con Composition-1k, cuya licencia restringe uso comercial; los resultados se usan en productos que se venden | Revisar la licencia antes de adoptarlo. Si no es apto, usar el matting clásico de pymatting (MIT) y evaluar alternativas con el golden set |
| R2 | La exportación de BiRefNet o ViTMatte a ONNX falla o pierde precisión | `scripts/export_models.py` compara salida PyTorch vs ONNX (error absoluto medio < 0.01) antes de publicar el modelo |
| R3 | `onnxruntime-gpu` requiere DLLs de CUDA/cuDNN compatibles | Instalar las dependencias CUDA vía pip en `.venv`; respaldo automático a CPU |
| R4 | La VRAM de la RTX 3050 no alcanza para matting a resolución completa | Matting por recortes alrededor del sujeto y por tiles |

## 6. Criterios de verificación

| Id | Criterio | Cómo se mide |
|---|---|---|
| V1 | Calidad en producto | Golden set de producto (mínimo 8 imágenes propias): IoU medio >= 0.97 contra máscara de referencia |
| V2 | Calidad en personas y mascotas | Golden set de personas/mascotas (mínimo 6 imágenes): SAD medio de alfa no peor que el de BiRefNet solo, y mejor en al menos el 70% de las imágenes con pelo |
| V3 | Sin regresiones | Cambiar modelo o ajustes no puede empeorar IoU ni SAD del golden set más de 2% sin aprobación explícita |
| V4 | Rendimiento GPU | Imagen de 4000x3000 en el equipo objetivo, pipeline completo con matting: <= 5 s (sin contar la primera carga del modelo) |
| V5 | Rendimiento CPU | La misma imagen sin GPU: <= 60 s |
| V6 | Refinar borde | Re-ejecutar matting en una región de 500x500 px: <= 2 s en GPU |
| V7 | Fidelidad del retoque | Máscara exportada idéntica píxel a píxel a la máscara del lienzo (test automático) |
| V8 | Deshacer | 50 trazos de pincel en imagen de 6000x4000 y deshacer todos devuelve la máscara original exacta; memoria del historial < 1 GB |
| V9 | Lote | 100 imágenes procesadas sin intervención, con informe CSV que lista el 100% de los archivos y sus estados |
| V10 | Fronteras | Test que falla si `core`, `engines` o `pipeline` importan PySide6 |
| V11 | Resiliencia | Archivo corrupto en un lote no detiene el lote y aparece como error en el informe |
| V12 | Codificación | Rutas y nombres de archivo con tildes y ñ se cargan y exportan correctamente |

## 7. Siguiente paso

Con la spec aprobada, convertirla en un plan de implementación paso a paso con la skill `plan`.
