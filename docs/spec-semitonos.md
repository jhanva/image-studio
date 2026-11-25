# Image Studio - Spec: Semitonos para DTF y sublimación

Estado: borrador para aprobación
Fecha: 2026-11-25
Autor: Johan (jhanva)

## 1. Problema y contexto

Al imprimir un diseño sobre una camiseta, las zonas del arte cercanas al color de la tela se ven
mejor si no llevan tinta: la camiseta hace de color. En DTF esto además ablanda el tacto y ahorra
tinta y polvo; en sublimación evita que el borde del diseño se vea como un parche. La técnica
consiste en:

1. **Knockout**: eliminar el color de la camiseta del arte.
2. **Degradado con semitonos**: convertir los colores cercanos al de la camiseta en puntos cuyo
   tamaño crece a medida que el color se aleja, hasta volverse tinta sólida.

La referencia de mercado es DTF-TONES Web, que hace esto en el navegador. Se estudió su
funcionamiento (ver sección 2) y se construye una herramienta propia, sin copiar su código ni
sus tablas, a partir de la teoría clásica de semitonos (función de punto, umbral por píxel y
trama de tangente racional).

Usos:

- **DTF y sublimación**, sobre camisetas oscuras o claras.
- **Entrada**: diseños gráficos (logos, ilustraciones, tipografía, arte con fondo sólido en PNG o
  JPG) y fotos ya recortadas con el quitafondos, con la misma frecuencia.
- **Una imagen a la vez**: la persona mueve los controles mirando la vista previa hasta que el
  resultado le gusta, y entonces exporta. La vista previa es el criterio de calidad.

La herramienta es independiente del quitafondos: para usarla sobre un recorte se exporta el PNG
desde el quitafondos y se abre en Semitonos. No hay botón de envío ni paso en el pipeline.

## 2. Enfoque elegido y justificación

**Trama por umbral calculada con numpy sobre la imagen completa (enfoque A)**, recalculada en
segundo plano por etapas con caché.

| Enfoque | Resultado |
|---|---|
| A. Umbral por píxel con numpy | Elegido. Una sola implementación: la vista previa es exactamente lo que se exporta |
| B. Puntos geométricos dibujados por celda | Descartado: unas 200 mil celdas por imagen; dibujarlas en Python tarda segundos |
| C. Vista previa en shader GPU y exportación con numpy | Descartado: dos implementaciones que deben coincidir píxel a píxel y un stack nuevo (GLSL) |

Lo observado en DTF-TONES Web confirma el enfoque A: su motor es JavaScript en un worker, sin GPU
ni IA, y procesa cada píxel con una tabla de umbrales. Un recálculo completo de 3600x4875 tarda
entre 0.8 y 1.3 s en el equipo del autor. Esa es la experiencia de referencia: mover un control
y ver el resultado en alrededor de un segundo.

## 3. Diseño detallado

### 3.1 Algoritmo por píxel

Entrada: imagen RGB `uint8` y alfa `float32` en [0, 1], ya a la resolución de impresión.

1. **Limpieza**: los píxeles marcados por la limpieza (3.3) o por el borrador **Borrar** quedan
   con alfa 0.
2. **Distancia al color de la camiseta** `k = (kr, kg, kb)`: para cada canal `c`,
   `d_c = (c - k_c) / (255 - k_c)` si `c > k_c`, y `d_c = (k_c - c) / k_c` si `c < k_c`
   (0 si el denominador es 0). La distancia es `d = max(d_r, d_g, d_b)`, en [0, 1].
3. **Cobertura**: `cov = min(1, d / alcance) ** gamma`, con `alcance` en (0, 1] y
   `gamma = 2 ** (-peso / 50)` para `peso` en [-100, 100]. Peso positivo pone más tinta.
4. **Semitransparencia**: modo **Tramar**: `cov *= alfa`. Modo **Corte al 50%**: los píxeles con
   alfa < 0.5 quedan eliminados y el resto ignora su alfa.
5. **Descartar puntos pequeños** con umbral `t`: `cov < t` pasa a 0 y `cov > 1 - t` pasa a 1.
6. **Bordes limpios** de `n` px: la zona con `cov == 1` se dilata `n` px (elemento en cruz) y
   esa dilatación, dentro de los píxeles visibles, pasa a `cov = 1`.
7. **Proteger**: los píxeles pintados con el borrador **Proteger** pasan a `cov = 1`.
8. **Trama**: el píxel lleva tinta si `cov > umbral(x, y)` (3.2). Los píxeles con `cov == 1`
   siempre llevan tinta y los de `cov == 0` nunca.
9. **Restaurar color de tinta** con fuerza `r` en [0, 1]: en píxeles con tinta y `cov < 1`,
   `color = k + (color - k) * (1 + (1 / cov - 1) * r)`, recortado a [0, 255]. Supone que el
   píxel original es una mezcla de tinta y camiseta y la deshace en la proporción `r`.
10. **Salida**: RGBA `uint8` con alfa binario (255 con tinta, 0 sin tinta) y RGB 0 donde no hay
    tinta. No hay alfa intermedio, como exige el film DTF.

### 3.2 Trama

- **Celda**: lado `L = dpi / lpi` px. Coordenadas de trama:
  `u = (x cos a + y sin a) / L`, `v = (-x sin a + y cos a) / L`, con `a` el ángulo.
- **Función de punto** `s(fu, fv)` sobre la parte fraccionaria centrada `fu, fv` en [-0.5, 0.5)
  (los patrones ondulados usan también `u` para la onda):

| Patrón | Función de punto (mayor valor = se entinta antes) |
|---|---|
| Redondo | `cos(2π fu) + cos(2π fv)` |
| Diamante | `-(abs(fu) + abs(fv))` |
| Elipse | `-(fu² + (1.6 fv)²)` |
| Cuadrado | `-max(abs(fu), abs(fv))` |
| Línea | `-abs(fv)` |
| Líneas onduladas | `-abs(fw)`, con `w = v - 0.15 sin(2π u / 4)` y `fw` su parte fraccionaria centrada |
| Puntos ondulados | `cos(2π fu) + cos(2π fw)`, con el mismo `w` |

Los patrones ondulados tienen un periodo de 4 celdas en `u`; los demás, de 1 celda.

- **Umbral**: `umbral = CDF_patrón(s)`, donde `CDF_patrón` es la fracción del área de un periodo
  completo del patrón con valor de punto mayor que `s`. Se precalcula una vez por patrón con un
  muestreo de 512x512 por periodo y se guarda como tabla de 4096 entradas. Así, en una zona de
  color plano, la fracción de píxeles con tinta es igual a la cobertura en todos los patrones.
- **Ajustar a la rejilla** (opción, activa por defecto): reemplaza el vector de celda por el
  vector entero `(p, q)` más cercano en ángulo cuyo largo difiere de `L` menos del 7%. La trama
  queda periódica sobre los píxeles y no genera moiré. La interfaz muestra el LPI y el ángulo
  efectivos (por ejemplo, 35 LPI a 22.5° pasa a 35.1 LPI a 20.6°).
- No se incluye curva de ganancia de punto propia de otro producto.

### 3.3 Limpieza

- **Quitar fondo sólido**: detecta el color dominante del borde de la imagen (moda de los píxeles
  opacos del marco de 1 px) y lo elimina con relleno por inundación desde el borde
  (`cv2.floodFill`), con tolerancia por canal.
- **Quitar también ese color dentro del arte**: elimina ese color en toda la imagen, incluidas
  zonas encerradas como el interior de las letras.
- **Borrar colores**: lista de colores elegidos con el cuentagotas; se eliminan en toda la imagen.
- **Tolerancia** en %: diferencia máxima por canal, `tolerancia * 255 / 100`.
- **Encoger borde** de `n` px: erosiona `n` px el contorno de lo visible.

### 3.4 Datos

| Modelo | Contenido |
|---|---|
| `HalftoneSettings` | Todos los parámetros de 3.1 a 3.3 y el ancho de impresión. Inmutable, serializable a JSON |
| `KnockoutMode` | `negro`, `blanco`, `auto` (negro o blanco, el más cercano al color medio del marco de 1 px) o `elegido` (color tomado con el cuentagotas) |
| `Pattern` | `redondo`, `diamante`, `elipse`, `cuadrado`, `linea`, `lineas_onduladas`, `puntos_ondulados` |
| `AlphaMode` | `tramar` o `cortar` |
| `EraseMask` | `uint8` HxW a resolución de impresión: 0 sin marca, 1 Borrar, 2 Proteger |
| `HalftonePreset` | `HalftoneSettings` con nombre. Incluidos: **Camiseta negra** (knockout negro) y **Camiseta blanca** (knockout blanco) |

Valores por defecto de `HalftoneSettings`:

| Parámetro | Valor | Rango |
|---|---|---|
| Color a eliminar | negro | ver `KnockoutMode` |
| Quitar fondo sólido | no | sí / no |
| Quitar ese color dentro del arte | no | sí / no |
| Tolerancia | 8% | 0 a 50% |
| Encoger borde | 0 px | 0 a 10 px |
| LPI | 35 | 10 a 85 |
| Ángulo | 22.5° | 0 a 180° |
| Ajustar a la rejilla | sí | sí / no |
| Patrón | redondo | ver `Pattern` |
| Alcance | 100% | 1 a 100% |
| Peso del punto | 0 | -100 a 100 |
| Descartar puntos pequeños | 3% | 0 a 20% |
| Semitransparencia | tramar | ver `AlphaMode` |
| Bordes limpios | 2 px | 0 a 10 px |
| Restaurar color de tinta | 50% | 0 a 100% |
| Ancho de impresión | ancho en px / DPI del archivo (300 si no trae DPI) | 1 a 30 pulgadas |
| DPI de impresión | 300 | fijo |

### 3.5 Componentes

```
src/image_studio/
  core/halftone/            # Python puro, sin Qt
    screen.py               # funciones de punto, tablas CDF, ajuste a la rejilla, campo de umbral
    knockout.py             # distancia, cobertura, descartar, bordes limpios, restaurar color
    cleanup.py              # fondo por inundación, borrar colores, tolerancia, encoger borde
    render.py               # combina las etapas sobre un rectángulo y devuelve RGBA binario
    settings.py             # HalftoneSettings, enums y validación de rangos
  pipeline/
    halftone_session.py     # imagen a resolución de impresión, EraseMask, historial, caché por etapas
    halftone_presets.py     # presets propios en %APPDATA%\ImageStudio\halftone_presets.json
  tools/halftone/
    panel.py                # Tool "Semitonos": controles, lienzo, cuentagotas, borradores, exportar
```

- `halftone_session` reutiliza `core.history.MaskHistory` sobre la `EraseMask` y
  `core.brush` para estampar los trazos.
- `panel` reutiliza `ui.canvas.CanvasView` (zoom, tablero, antes/después, cursor de pincel) y
  `workers.ejecutar` para el cálculo en segundo plano.
- `ui/app.py` agrega la herramienta en `crear_herramientas`. Ninguna otra herramienta cambia.

### 3.6 Caché por etapas

| Etapa | Contenido | Se recalcula cuando cambia |
|---|---|---|
| E1 Imagen de impresión | RGB y alfa remuestreados (Lanczos) al ancho de impresión a 300 DPI | Ancho de impresión |
| E2 Visible | Alfa tras limpieza, Borrar y modo de semitransparencia | E1, limpieza, `EraseMask` (zona tocada), semitransparencia |
| E3 Cobertura | `cov` `float32` tras pasos 2 a 7 de 3.1 | E2, color a eliminar, alcance, peso, descartar, bordes limpios, Proteger |
| E4 Umbral | Campo de umbral `uint16` HxW | Tamaño de E1, LPI, ángulo, patrón, ajustar a la rejilla |
| E5 Salida | RGBA binario con color restaurado | Cualquiera de las anteriores o restaurar color |

Mover un control recalcula solo desde su etapa. Al cambiar el ancho de impresión, la
`EraseMask` se remuestrea por vecino más cercano y el historial se reinicia.

### 3.7 Flujo en la interfaz

1. **Abrir** una imagen (diálogo o arrastrar y soltar), con los mismos formatos de entrada que el
   quitafondos.
2. **Ajustar** controles agrupados como en 3.4. Cada cambio incrementa un número de generación y
   lanza el cálculo tras 150 ms sin nuevos cambios.
3. **Calcular en segundo plano**: primero el rectángulo visible del lienzo (más un margen igual a
   bordes limpios) y luego la imagen completa. Un resultado con generación vieja se descarta. El
   cálculo comprueba la generación entre etapas y abandona si quedó vieja.
4. **Ver** en modo **Camiseta** (fondo del color de la camiseta, editable, por defecto el color a
   eliminar) o **Transparente** (tablero), con antes/después, zoom y ajuste a la ventana.
5. **Cuentagotas**: un clic en el lienzo toma el color a eliminar o agrega un color a borrar.
6. **Borradores**: pinceles **Borrar**, **Proteger** y **Quitar marca** (vuelve a 0), con tamaño en
   pulgadas de impresión (teclas `[` y `]`), deshacer y rehacer (Ctrl+Z, Ctrl+Y) y **Limpiar
   todo**.
7. **Presets**: elegir, guardar con nombre y borrar presets propios. Guardan solo
   `HalftoneSettings`, no los trazos.
8. **Exportar** PNG RGBA con 300 DPI en los metadatos, a la resolución de impresión y sin
   recorte. Si el resultado no tiene ningún píxel con tinta, se avisa antes de guardar.

### 3.8 Casos límite

| Caso | Manejo |
|---|---|
| Arte JPG con artefactos alrededor del fondo | Subir tolerancia; encoger borde para quitar el halo |
| Foto recortada con bordes semitransparentes | Modo Tramar degrada el borde; modo Corte al 50% lo deja nítido |
| Texto pequeño o caras que no deben tramarse | Borrador Proteger |
| Color de camiseta igual a todo el arte | La salida queda sin tinta y la exportación lo avisa |
| Imagen de impresión de más de 60 MP | Se limita el ancho de impresión al máximo que da 60 MP y se informa en la barra de estado |
| Cambiar el ancho después de pintar | La `EraseMask` se remuestrea; el historial se reinicia con aviso |
| Imagen sin fondo sólido en el borde | Quitar fondo sólido no elimina nada y lo informa |
| Rutas con tildes y ñ | Se cargan y exportan correctamente (como V12 de la spec principal) |

### 3.9 Pruebas

- **Unidad (`core/halftone`)**, con imágenes sintéticas generadas en la prueba:
  - fracción de tinta en zonas planas igual a la cobertura para cada patrón;
  - distancia y cobertura en colores conocidos;
  - descartar, bordes limpios, Proteger y restaurar color;
  - periodicidad entera del campo de umbral con ajuste a la rejilla;
  - limpieza por inundación frente a colores encerrados.
- **Sesión**: caché por etapas (qué se recalcula según el parámetro que cambia), descarte por
  generación, deshacer de borradores y remuestreo de la `EraseMask`.
- **Interfaz (pytest-qt)**: abrir, mover un control, recibir la vista previa, pintar, deshacer
  y exportar.
- **Rendimiento**: script de medición en el equipo objetivo; no forma parte de `pytest`.
- El test de fronteras existente cubre `core/halftone` y los módulos nuevos de `pipeline`.

## 4. Decisiones explícitas

### Incluido

- Herramienta **Semitonos** en la barra lateral de la suite, una imagen a la vez.
- Knockout con modos negro, blanco, automático y elegido.
- Degradado con alcance, peso, descartar puntos pequeños, semitransparencia, bordes limpios y
  restaurar color.
- Trama con LPI, ángulo, ajuste a la rejilla y siete patrones.
- Limpieza: fondo sólido, color dentro del arte, colores elegidos, tolerancia y encoger borde.
- Borradores Borrar, Proteger y Quitar marca con deshacer.
- Vista previa en camiseta o transparente, recalculada en segundo plano.
- Presets incluidos y propios.
- Exportación PNG RGBA a 300 DPI con alfa binario.

### Excluido

- Integración con el quitafondos (botón de envío o paso de pipeline).
- Lotes y línea de comandos.
- Exportación vectorial, separación de colores o tramas por canal (CMYK).
- Curva de ganancia de punto de otro producto.
- Aceleración por GPU.
- Exportación JPG o WebP (el film necesita PNG con alfa).

## 5. Riesgos

| Id | Riesgo | Mitigación |
|---|---|---|
| R1 | El recálculo completo con numpy supera el objetivo de S1 en imágenes grandes | Etapas con caché, cálculo del rectángulo visible primero y `float32`; si aun así no alcanza, campo de umbral con `numba` como cambio aislado en `screen.py` |
| R2 | Moiré en la vista previa con zoom de ajuste | La vista reduce con suavizado; la exportación es a resolución completa. Se recomienda revisar al 100% |
| R3 | Memoria con imágenes grandes (varias matrices HxW) | Límite de 60 MP y tipos compactos (`uint8`, `uint16`, `float32`) |

## 6. Criterios de verificación

| Id | Criterio | Cómo se mide |
|---|---|---|
| S1 | Vista previa completa | 3600x4800 en el equipo objetivo: <= 1.5 s desde el último cambio hasta la imagen completa actualizada (referencia: 0.8 a 1.3 s de DTF-TONES Web) |
| S2 | Vista previa al 100% | Rectángulo visible de 1920x1080: <= 300 ms desde el último cambio |
| S3 | Linealidad | En zonas planas de 512x512, la fracción de píxeles con tinta difiere de la cobertura en menos de 0.02 para cada patrón y cobertura de 0.1 a 0.9 |
| S4 | Knockout | Píxeles con el color exacto de la camiseta: 0 píxeles con tinta |
| S5 | Puntos pequeños | Zona plana con cobertura menor que el umbral de descartar: 0 píxeles con tinta |
| S6 | Alfa binario | La exportación solo contiene alfa 0 o 255 y declara 300 DPI |
| S7 | Fidelidad | La exportación es idéntica píxel a píxel a la última vista previa completa |
| S8 | Proteger | Los píxeles visibles pintados con Proteger salen sólidos (alfa 255, color original) |
| S9 | Rejilla | Con ajuste a la rejilla, el campo de umbral se repite exactamente al desplazarse un periodo del patrón: el vector `(p, q)` en los patrones de 1 celda y `4 (p, q)` en los ondulados |
| S10 | Caché | Cambiar solo el LPI no recalcula E1, E2 ni E3 (test con contadores) |
| S11 | Deshacer | 50 trazos de borrador deshechos devuelven la `EraseMask` original exacta |
| S12 | Fronteras | `core/halftone` y los módulos nuevos de `pipeline` no importan PySide6 |

## 7. Siguiente paso

Con la spec aprobada, convertirla en un plan de implementación (`docs/plans/`) con la skill
`plan`.
