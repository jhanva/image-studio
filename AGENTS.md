# Reglas de trabajo - image-studio

Estas reglas aplican a todo el repositorio desde Claude Code y Codex. El flujo detallado de
ramas, commits, pull requests y versiones vive en [docs/repo-workflow.md](docs/repo-workflow.md).
El alcance y el diseño de la app viven en [docs/spec.md](docs/spec.md).

## Alcance

- Trabajar en español. Los textos de la UI y la documentación usan tildes y ñ.
- App de escritorio Windows para uso personal: suite de herramientas de imagen en
  Python + PySide6. La primera herramienta es quitar fondos.
- `core/`, `engines/` y `pipeline/` no importan PySide6. Cada herramienta nueva implementa la
  interfaz `Tool` sin modificar las demás.
- No inventar modelos, pesos, licencias ni hashes. Comprobarlos o declarar la incertidumbre.
- Sin emojis en código, comentarios, commits ni textos de la UI.

## Entorno obligatorio

- Ejecutar todo Python y pip desde el `.venv` de la raíz: `.\.venv\Scripts\python.exe -X utf8`.
  No usar Python global, `py` ni otro entorno. Un Python base solo sirve para recrear `.venv`.
- Dependencias de la app en `requirements.txt`; pruebas y exportación de modelos en
  `requirements-dev.txt`.

## Autorización

Se puede leer y editar el repo, ejecutar pruebas, crear ramas, commits y PR, e integrar un PR
que cumpla la lista de verificación de [docs/repo-workflow.md](docs/repo-workflow.md).

Requiere permiso explícito para cada caso:

- escribir directo sobre `main` o `develop`
- reescribir historial o usar `push --force`, `rebase` publicado o `reset --hard`
- borrar o renombrar `main` o `develop`
- cambiar configuración de GitHub, credenciales, o agregar, quitar o cambiar de versión un
  modelo de IA
- actuar sobre un servicio externo, salvo cuando el usuario haya pedido expresamente ese flujo

## Edición y seguridad

- No crear `output/`, `tmp/`, `temp/` ni equivalentes dentro del repo.
- El repositorio es público. Nunca versionar fotos de clientes, personas reales ni imágenes
  sin licencia libre. El golden set privado vive fuera del repo (ver `docs/spec.md`); en
  `tests/` solo van imágenes sintéticas o con licencia que permita redistribuirlas.
- No mencionar nombres de clientes ni de negocios en código, documentación ni commits.
- No crear copias con sufijos `copia`, `nuevo`, `final` o `v2`.
- Usar UTF-8 sin BOM y respetar `.gitattributes`.
- Preservar cambios ajenos y evitar comandos destructivos.

## Verificación y cierre

Antes de cada commit ejecutar:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest
```

No declarar éxito sin leer la salida. Al cerrar, indicar archivos modificados, verificaciones
realizadas y cualquier limitación pendiente.
