# Flujo del repositorio

Adaptado de `ai-skills/docs/repo-workflow.md` para una aplicación Python de escritorio.

## Gitflow

`main` contiene lo publicado y `develop` lo integrado pendiente de publicar. Todo
cambio nace desde la rama permanente actualizada y entra por pull request.

| Origen | Destino | Integración | Borrar origen |
|---|---|---|---|
| `feature/`, `fix/`, `agent/` | `develop` | squash | sí |
| `hotfix/` | `main` | squash | no |
| `main` tras hotfix | `develop` | merge commit | no aplica |
| `develop` | `main` | merge commit | nunca |

Antes de ramificar: `git fetch --prune`, `git checkout develop` y
`git pull --ff-only`. Una rama desechable solo se elimina cuando su contenido está
en `develop`.

## Commits y pull requests

Los commits usan Conventional Commits en español:

```text
<tipo>(<alcance>): <descripción imperativa>
```

Tipos: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`
y `revert`. La primera línea usa minúsculas, no termina en punto y no supera 72
caracteres. No se agregan trailers ni atribuciones de asistentes.

Alcances habituales: `core`, `engines`, `pipeline`, `ui`, `tools`, `cli`, `models`,
`spec`, `repo`.

Un pull request explica qué cambia, por qué, archivos afectados, pruebas y modelos
tocados. Antes de integrarlo:

1. la rama no tiene conflictos con el destino
2. `.\.venv\Scripts\python.exe -X utf8 -m pytest` pasa
3. si toca `engines/`, `pipeline/` o modelos, el golden set de calidad pasa sin regresiones
4. no incluye settings locales, cachés, temporales, modelos descargados ni credenciales
5. la spec y la documentación reflejan el comportamiento modificado
6. usa el modo de integración de la tabla anterior

## Versiones

- La versión de la app sigue SemVer y vive en un único lugar: `pyproject.toml`.
- Se incrementa en la rama que integra `develop` en `main` (o en el `hotfix/`), nunca en
  ramas de feature.
- Cada integración en `main` se etiqueta como `vX.Y.Z`.
- Cambiar un modelo (archivo, versión o hash en `model_manager`) se anota en el PR y en
  el changelog de la versión.

## Archivos y salidas

- texto UTF-8 sin BOM
- LF por defecto y en `.sh`; CRLF en `.ps1`
- temporales fuera del repositorio
- no versionar `.venv/`, `.claude/settings.local.json`, `__pycache__/`, modelos `.onnx`,
  secretos ni entornos
- un único archivo vigente por asunto; no usar sufijos `copia`, `nuevo`, `final`, `v2`
