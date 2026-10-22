import pytest

from image_studio.engines.matting_classic import ClassicMatter
from image_studio.engines.model_manager import MODELOS, models_dir
from image_studio.pipeline.factory import build_remover


def test_modelo_desconocido():
    with pytest.raises(ValueError, match="Modelo"):
        build_remover("u2net")


@pytest.mark.model
@pytest.mark.parametrize("modelo", sorted(MODELOS))
def test_construye_con_modelo_descargado(modelo):
    if not (models_dir() / MODELOS[modelo].archivo).exists():
        pytest.skip(f"Modelo {modelo} no descargado")
    removedor = build_remover(modelo, dispositivo="cpu")
    assert removedor.segmentador.nombre == modelo
    assert isinstance(removedor.matter, ClassicMatter)
