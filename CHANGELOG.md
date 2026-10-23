# Cambios

## 0.3.0 - 2026-10-23

Primera versión publicada. Completa el MVP de [docs/spec.md](docs/spec.md).

### Motor y línea de comandos (Hito 1)

- Carga de JPG, PNG, WebP, BMP, TIFF y HEIC con orientación EXIF, CMYK, 16 bits y alfa existente.
- Segmentación con BiRefNet (calidad) e ISNet (rápido) sobre ONNX Runtime, con CUDA y respaldo a CPU.
- Matting clásico por bloques en hilos, limpieza de color en bordes y ajustes de borde.
- Presets producto y persona, detección de baja confianza.
- Exportación PNG, WebP y JPG con fondo transparente, blanco o de color, recorte, margen y DPI.
- `python -m image_studio batch ENTRADA SALIDA` con informe CSV.

### Editor (Hito 2)

- `python -m image_studio [IMAGEN]` abre el editor: abrir, arrastrar y soltar, pegar.
- Lienzo con tablero de transparencia, zoom, desplazamiento y vista del original.
- Pinceles Conservar, Borrar y Refinar borde; deshacer y rehacer por tiles.

### Suite (Hito 3)

- Barra lateral de herramientas: Quitar fondo y Lotes.
- Lotes en la interfaz con progreso, cancelación y apertura de resultados en el editor.
- Presets propios en `%APPDATA%\ImageStudio\presets.json`.
- Diálogo de exportación completo.

### Modelos

- BiRefNet general: `58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c`
- ISNet general-use: `60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a`
- ViTMatte no se adopta (licencia de los pesos, riesgo R1 de la spec).

### Rendimiento medido (RTX 3050 8 GB, imagen de 4000x3000)

- Preset persona en GPU: 4.5 s. Preset producto en GPU: 2.8 s. Persona en CPU: 28 s.
- Refinar borde en una región de 500x500: menos de 1 s.
