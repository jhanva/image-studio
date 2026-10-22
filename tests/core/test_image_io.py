import numpy as np
import pytest
from PIL import Image

from image_studio.core.image_io import ImageLoadError, load_image


def test_carga_png_rgb(escribir_png, tmp_path):
    doc = load_image(escribir_png(tmp_path / "a.png", ancho=20, alto=10))
    assert doc.rgb.shape == (10, 20, 3)
    assert doc.rgb.dtype == np.uint8
    assert doc.alpha is None
    assert doc.size == (20, 10)


def test_conserva_alfa_existente(tmp_path):
    ruta = tmp_path / "alfa.png"
    Image.new("RGBA", (4, 4), (10, 20, 30, 128)).save(ruta)
    doc = load_image(ruta)
    assert doc.alpha.dtype == np.float32
    assert doc.alpha[0, 0] == pytest.approx(128 / 255)
    assert tuple(doc.rgb[0, 0]) == (10, 20, 30)


def test_aplica_orientacion_exif(tmp_path):
    ruta = tmp_path / "rotada.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (20, 10)).save(ruta, exif=exif)
    assert load_image(ruta).rgb.shape == (20, 10, 3)


def test_ruta_con_tildes_y_enie(escribir_png, tmp_path):
    doc = load_image(escribir_png(tmp_path / "canción ñandú.png"))
    assert doc.path.name == "canción ñandú.png"


def test_convierte_cmyk(tmp_path):
    ruta = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (8, 8), (0, 0, 0, 0)).save(ruta)
    assert load_image(ruta).rgb.shape == (8, 8, 3)


def test_convierte_png_de_16_bits(tmp_path):
    ruta = tmp_path / "gris16.png"
    Image.new("I;16", (4, 4), 65535).save(ruta)
    doc = load_image(ruta)
    assert doc.rgb.shape == (4, 4, 3)
    assert (doc.rgb == 255).all()


def test_lee_dpi(tmp_path):
    ruta = tmp_path / "dpi.png"
    Image.new("RGB", (4, 4)).save(ruta, dpi=(300, 300))
    assert load_image(ruta).dpi == pytest.approx((300, 300), abs=0.01)


def test_archivo_corrupto(tmp_path):
    ruta = tmp_path / "roto.png"
    ruta.write_bytes(b"no es una imagen")
    with pytest.raises(ImageLoadError, match="roto.png"):
        load_image(ruta)


def test_formato_no_soportado(tmp_path):
    with pytest.raises(ImageLoadError, match="Formato no soportado"):
        load_image(tmp_path / "animacion.gif")
