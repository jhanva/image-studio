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
