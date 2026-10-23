import numpy as np
import pytest
from PIL import Image

from image_studio.core.export import ExportSettings, Fondo, compose, save


def _rojo_con_cuadro(n: int = 10):
    rgb = np.zeros((n, n, 3), np.uint8)
    rgb[...] = (255, 0, 0)
    alfa = np.zeros((n, n), np.float32)
    alfa[2:5, 2:5] = 1.0
    return rgb, alfa


def test_transparente_agrega_canal_alfa():
    salida = compose(*_rojo_con_cuadro(), ExportSettings())
    assert salida.shape == (10, 10, 4)
    assert salida[3, 3, 3] == 255 and salida[0, 0, 3] == 0


def test_fondo_blanco():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(fondo=Fondo.BLANCO))
    assert salida.shape == (10, 10, 3)
    assert tuple(salida[0, 0]) == (255, 255, 255)
    assert tuple(salida[3, 3]) == (255, 0, 0)


def test_fondo_de_color():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(fondo=Fondo.COLOR, color=(0, 128, 0)))
    assert tuple(salida[0, 0]) == (0, 128, 0)


def test_jpg_transparente_usa_blanco():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(formato="jpg"))
    assert salida.shape == (10, 10, 3)
    assert tuple(salida[0, 0]) == (255, 255, 255)


def test_recorta_al_contenido_con_margen():
    salida = compose(*_rojo_con_cuadro(), ExportSettings(recortar=True, margen_px=1))
    assert salida.shape == (5, 5, 4)


def test_recortar_mascara_vacia_no_recorta():
    rgb, _ = _rojo_con_cuadro()
    salida = compose(rgb, np.zeros((10, 10), np.float32), ExportSettings(recortar=True))
    assert salida.shape == (10, 10, 4)


def test_png_conserva_mascara_pixel_a_pixel(tmp_path):
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
    alfa = rng.random((32, 32)).astype(np.float32)
    ruta = save(compose(rgb, alfa, ExportSettings()), tmp_path / "v7.png", ExportSettings())
    with Image.open(ruta) as imagen:
        guardado = np.array(imagen)
    esperado = np.clip(alfa * 255.0 + 0.5, 0, 255).astype(np.uint8)
    assert np.array_equal(guardado[..., 3], esperado)
    assert np.array_equal(guardado[..., :3], rgb)


def test_cambia_la_extension_segun_formato(tmp_path):
    ruta = save(compose(*_rojo_con_cuadro(), ExportSettings()), tmp_path / "a.jpg", ExportSettings())
    assert ruta.name == "a.png" and ruta.exists()


def test_ruta_con_tildes_y_dpi(tmp_path):
    ajustes = ExportSettings(dpi=300)
    ruta = save(compose(*_rojo_con_cuadro(), ajustes), tmp_path / "salida ñ" / "canción.png", ajustes)
    with Image.open(ruta) as imagen:
        assert imagen.info["dpi"] == pytest.approx((300, 300), abs=0.01)


def test_formato_invalido():
    with pytest.raises(ValueError):
        ExportSettings(formato="gif")
