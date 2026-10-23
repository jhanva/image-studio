# Image Studio

Suite de escritorio Windows para manipular imágenes. Primera herramienta: quitar fondos con
calidad profesional, procesando todo en local.

- Diseño y alcance: [docs/spec.md](docs/spec.md)
- Flujo de ramas, commits y PR: [docs/repo-workflow.md](docs/repo-workflow.md)
- Reglas para agentes: [AGENTS.md](AGENTS.md)

## Uso (Hito 1: línea de comandos)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch fotos salida --preset producto
.\.venv\Scripts\python.exe -X utf8 -m image_studio batch fotos salida --preset persona --fondo blanco --formato jpg --recortar --margen 40
```

La primera ejecución descarga el modelo a `%LOCALAPPDATA%\ImageStudio\models`. Cada lote deja
`informe.csv` en la carpeta de salida.

## Uso (Hito 2: editor)

```powershell
.\.venv\Scripts\python.exe -X utf8 -m image_studio
.\.venv\Scripts\python.exe -X utf8 -m image_studio D:\fotos\termo.jpg
```

Atajos: Ctrl+O abrir, Ctrl+V pegar, Ctrl+R quitar fondo, V mover, K conservar, E borrar,
R refinar borde, Ctrl+Z deshacer, Ctrl+Y rehacer, B ver original, Ctrl+0 ajustar, Ctrl+1 100%,
Ctrl+S guardar PNG. Rueda: zoom. Botón central: desplazar.

## Uso (Hito 3: suite)

La barra lateral cambia entre **Quitar fondo** (editor) y **Lotes**. En Lotes se eligen las
carpetas, el preset y la exportación; doble clic en una fila abre esa imagen en el editor para
retocarla. Los presets propios se guardan en `%APPDATA%\ImageStudio\presets.json`.

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
