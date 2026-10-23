# Construye dist\ImageStudio con dos ejecutables que comparten las mismas bibliotecas:
#   ImageStudio.exe        interfaz, sin consola
#   image-studio-cli.exe   batch, preparar y diagnostico, con consola
# Uso: .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist --workpath build packaging\image_studio.spec
import sysconfig
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

RAIZ = Path(SPECPATH).parent
SITE = Path(sysconfig.get_paths()["purelib"])
DLLS_NVIDIA = [(str(p), str(p.parent.relative_to(SITE))) for p in (SITE / "nvidia").rglob("*.dll")]

a = Analysis(
    [str(RAIZ / "packaging" / "lanzador.py")],
    pathex=[str(RAIZ / "src")],
    binaries=DLLS_NVIDIA,
    datas=copy_metadata("pymatting") + copy_metadata("image-studio"),
    hiddenimports=["image_studio.ui.app"],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyInstaller"],
    # numba guarda su caché junto a la fuente; pymatting necesita los .py en disco.
    module_collection_mode={"pymatting": "pyz+py"},
)
# El proveedor TensorRT depende de DLL que no se distribuyen.
a.binaries = [b for b in a.binaries if "tensorrt" not in b[0].lower()]
pyz = PYZ(a.pure)
# Equivale a python -X utf8, como exige AGENTS.md.
OPCIONES = [("X utf8", None, "OPTION")]
interfaz = EXE(pyz, a.scripts, OPCIONES, exclude_binaries=True, name="ImageStudio", console=False)
consola = EXE(pyz, a.scripts, OPCIONES, exclude_binaries=True, name="image-studio-cli", console=True)
COLLECT(interfaz, consola, a.binaries, a.datas, name="ImageStudio")
