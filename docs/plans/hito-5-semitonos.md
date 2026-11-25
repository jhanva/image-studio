# Plan de implementación - Hito 5: semitonos

Spec: [../spec-semitonos.md](../spec-semitonos.md). Flujo: [../repo-workflow.md](../repo-workflow.md).
Rama: `feature/hito-5-semitonos` desde `develop`. Un commit por tarea; PR a `develop` (squash) al final.

## Objetivo del hito

Agregar a la suite la herramienta **Semitonos**: elimina el color de la camiseta y degrada con
semitonos la zona cercana, con vista previa que se recalcula en segundo plano mientras se mueven
los controles, y exporta PNG con alfa binario a 300 DPI. Es independiente del quitafondos.

## Reutilización

| Pieza existente | Uso en este hito |
|---|---|
| `core.image_io.load_image`, `ImageDoc` | Abrir la imagen (RGB uint8, alfa float32 o None, DPI) |
| `core.export.save` | Escribir el PNG RGBA con 300 DPI |
| `core.history.MaskHistory` | Deshacer y rehacer sobre la `EraseMask` uint8 |
| `core.brush.brush_profile`, `footprint_rect`, `huella_en`, `stroke_points` | Trazos de los borradores |
| `pipeline.presets_store.config_dir` | Carpeta de `halftone_presets.json` |
| `ui.canvas.CanvasView`, `ui.qt_image.RgbaBuffer` | Lienzo con zoom, antes/después y pincel |
| `workers.ejecutar` | Cálculo en segundo plano |
| `tests/test_boundaries.py` | Ya recorre `core/` y `pipeline/` completos: cubre S12 |

## Mapa de archivos

- Crear (sin Qt): `src/image_studio/core/halftone/__init__.py`, `settings.py`, `screen.py`,
  `knockout.py`, `cleanup.py`, `render.py`; `src/image_studio/pipeline/halftone_session.py`,
  `src/image_studio/pipeline/halftone_presets.py`; `scripts/bench_halftone.py`
- Crear (Qt): `src/image_studio/tools/halftone/__init__.py`, `src/image_studio/tools/halftone/panel.py`
- Modificar: `src/image_studio/ui/canvas/view.py`, `src/image_studio/ui/app.py`, `README.md`
- Tests nuevos: `tests/core/halftone/test_settings.py`, `test_screen.py`, `test_knockout.py`,
  `test_cleanup.py`, `test_render.py`; `tests/pipeline/test_halftone_session.py`,
  `tests/pipeline/test_halftone_presets.py`; `tests/tools/test_halftone_tool.py`
- Tests modificados: `tests/ui/test_view.py`, `tests/ui/test_app.py`

Comandos desde la raíz del repo en PowerShell. Cada tarea sigue RED-GREEN: escribir el test,
verlo fallar, implementar, verlo pasar y ejecutar la suite completa antes del commit:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```

---

## Fase A - Núcleo sin Qt

### Tarea 1: spec y plan

Commit de `docs/spec-semitonos.md`, el enlace en `docs/spec.md` (sección 8) y este plan.
`docs(spec): definir la herramienta de semitonos`.

### Tarea 2: ajustes

`core/halftone/settings.py`: enums `KnockoutMode`, `Pattern`, `AlphaMode`; `HalftoneSettings`
inmutable con los valores por defecto y rangos de la tabla 3.4 de la spec, validación en
`__post_init__`, propiedad `gamma = 2 ** (-peso / 50)`, `to_dict` y `from_dict` (ignora claves
desconocidas y rechaza valores fuera de rango).

Tests: valores por defecto, rangos inválidos, ida y vuelta por JSON, gamma en -100, 0 y 100.

### Tarea 3: trama

`core/halftone/screen.py`:

- funciones de punto de la tabla 3.2 (redondo, diamante, elipse, cuadrado, línea, líneas
  onduladas, puntos ondulados), periodo de 1 celda o 4 celdas en `u`;
- `cdf_table(pattern)`: muestreo de un periodo con 512 muestras por celda y lado, 4096 entradas
  ordenadas, en caché;
- `snap_screen(celda, angulo)`: vector entero `(p, q)` más cercano en ángulo con largo a menos
  del 7% de la celda; devuelve vector, LPI y ángulo efectivos;
- `threshold_field(rect, ajustes)`: umbral `uint16` en [0, 65535] del rectángulo.

Tests: S3 (fracción entintada frente a cobertura, error < 0.02, cobertura 0.1 a 0.9, cada patrón,
LPI 35 a 300 DPI, zona de 512x512) y S9 (periodicidad exacta con ajuste a la rejilla).

### Tarea 4: knockout y cobertura

`core/halftone/knockout.py`: `distance(rgb, k)`, `coverage(dist, alcance, gamma)`,
`apply_alpha`, `drop_small`, `clean_edges` (`cv2.dilate` con cruz de 3x3, `n` iteraciones),
`restore_ink`, `auto_knockout(rgb, alpha)`.

Tests: distancia en colores conocidos, S4 (color exacto da cobertura 0), S5 (bajo el umbral da 0),
bordes limpios, restaurar color y color automático.

### Tarea 5: limpieza

`core/halftone/cleanup.py`: `border_color`, `cleanup_mask(rgb, alpha, ajustes)` con inundación
desde el borde (`cv2.floodFill`, `FLOODFILL_FIXED_RANGE`), color dentro del arte, colores
borrados y encoger borde (`cv2.erode`).

Tests con una letra sintética cuyo interior tiene el color del fondo: sin la opción de color
interior el hueco se conserva; con ella se elimina.

### Tarea 6: render por etapas

`core/halftone/render.py`: `visible_alpha` (E2), `coverage_map` (E3), `threshold_field` (E4) y
`compose_output` (E5) sobre un rectángulo, y `render` que las combina.

Tests: S6 (alfa solo 0 o 255), cobertura 1 siempre con tinta, cobertura 0 nunca, S8 (Proteger).

### Tarea 7: medición temprana

`scripts/bench_halftone.py`: imagen sintética de 3600x4800, tiempos por etapa, total y rectángulo
de 1920x1080. Los resultados se anotan en la sección "Mediciones" de este plan. Si no cumplen S1
(<= 1.5 s) o S2 (<= 300 ms), se optimiza dentro de numpy y OpenCV antes de seguir.

## Fase B - Sesión y presets

### Tarea 8: sesión

`pipeline/halftone_session.py`: `HalftoneSession(doc)` con remuestreo al ancho de impresión
(Lanczos, límite de 60 MP), `EraseMask` con `MaskHistory`, trazos con modos Borrar, Proteger y
Quitar marca, deshacer y rehacer, caché por etapas (tabla 3.6 de la spec) con contadores,
número de generación con abandono entre etapas, `render(rect, generacion)`, `hay_tinta` y
`export(ruta)`.

Tests: S7 (exportación igual a la vista previa), S10 (cambiar LPI no recalcula E1 a E3), S11
(50 trazos deshechos), remuestreo de la máscara al cambiar el ancho, descarte por generación.

### Tarea 9: presets

`pipeline/halftone_presets.py`: `HalftonePresetStore` en `config_dir() / "halftone_presets.json"`
con **Camiseta negra** y **Camiseta blanca** incluidos, mismo comportamiento que `PresetStore`
ante nombres inválidos y archivos corruptos.

## Fase C - Interfaz

### Tarea 10: fondo sólido en el lienzo

`CanvasView.set_fondo(color | None)`: con color, `drawBackground` pinta ese color en lugar del
tablero. Test en `tests/ui/test_view.py`.

### Tarea 11: panel Semitonos

`tools/halftone/panel.py`: `HalftoneTool(Tool)`, id `semitonos`, con todo lo descrito en la
sección 3.7 de la spec. Tests pytest-qt: abrir, mover un control y recibir la vista previa,
pintar y deshacer, exportar y aviso sin tinta.

### Tarea 12: registro y documentación

Agregar `HalftoneTool` en `crear_herramientas` (`ui/app.py`), ajustar `tests/ui/test_app.py` y
documentar el uso en `README.md`.

## Fase D - Verificación

### Tarea 13: cierre

Suite completa, medición S1 y S2 en la app real, prueba manual con un diseño sintético y PR a
`develop` con la lista de verificación de `docs/repo-workflow.md`.

## Mediciones

Se completan en la tarea 7.
