import subprocess
import sys


def test_importar_los_motores_no_carga_pymatting():
    codigo = (
        "import sys\n"
        "import image_studio.engines.matting_classic, image_studio.engines.decontaminate\n"
        "import image_studio.pipeline.session\n"
        "print('pymatting' in sys.modules)\n"
    )
    salida = subprocess.run([sys.executable, "-X", "utf8", "-c", codigo], capture_output=True, text=True, check=True)
    assert salida.stdout.strip() == "False"


def test_preparar_carga_pymatting():
    from image_studio.engines import decontaminate, matting_classic
    from image_studio.engines.warmup import prepare_engines

    assert prepare_engines() >= 0.0
    assert matting_classic.estimate_alpha_cf is not None
    assert matting_classic.ichol is not None
    assert decontaminate.estimate_foreground_ml is not None
