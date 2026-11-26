import numpy as np

from image_studio.core.halftone.cleanup import border_color, cleanup_mask
from image_studio.core.halftone.settings import HalftoneSettings

FONDO = (250, 250, 250)
TINTA = (20, 40, 200)


def _letra_o():
    """Fondo claro con un anillo de tinta cuyo interior tiene el color del fondo."""
    rgb = np.full((40, 40, 3), FONDO, np.uint8)
    yy, xx = np.mgrid[:40, :40]
    r = np.hypot(yy - 20, xx - 20)
    rgb[(r >= 8) & (r <= 14)] = TINTA
    return rgb, np.ones((40, 40), np.float32), r


def test_color_del_borde():
    rgb, alfa, _ = _letra_o()
    rgb[0, :3] = (1, 2, 3)
    assert border_color(rgb, alfa) == FONDO
    assert border_color(rgb, np.zeros_like(alfa)) is None


def test_quitar_fondo_conserva_el_hueco_encerrado():
    rgb, alfa, r = _letra_o()
    res = cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True))
    assert res.fondo == FONDO
    assert res.eliminado[0, 0] and res.eliminado[r > 16].all()
    assert not res.eliminado[r < 6].any()
    assert not res.eliminado[(r >= 8) & (r <= 14)].any()


def test_quitar_fondo_interior_elimina_tambien_el_hueco():
    rgb, alfa, r = _letra_o()
    res = cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True, fondo_interior=True))
    assert res.eliminado[r < 6].all() and res.eliminado[r > 16].all()


def test_tolerancia_para_artefactos_jpg():
    rgb, alfa, r = _letra_o()
    yy, xx = np.mgrid[:40, :40]
    rgb[(r > 16) & ((yy + xx) % 2 == 1)] = (240, 245, 250)  # ruido alrededor del color dominante
    assert not cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True, tolerancia=0))\
        .eliminado[r > 17].all()
    assert cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True, tolerancia=8))\
        .eliminado[r > 17].all()


def test_borrar_colores_y_encoger():
    rgb, alfa, r = _letra_o()
    res = cleanup_mask(rgb, alfa, HalftoneSettings(colores_borrar=[TINTA]))
    assert res.eliminado[(r >= 8) & (r <= 14)].all() and not res.eliminado[0, 0]
    encogido = cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True, encoger_px=2))
    anillo = (r >= 8) & (r <= 14)
    assert encogido.eliminado[anillo & (r > 13.5)].any()
    assert not encogido.eliminado[(r >= 10.5) & (r <= 11.5)].any()


def test_lo_transparente_deja_pasar_la_inundacion():
    rgb, alfa, r = _letra_o()
    alfa[:, :2] = 0.0
    rgb[:, :2] = (0, 0, 0)
    res = cleanup_mask(rgb, alfa, HalftoneSettings(quitar_fondo=True))
    assert res.eliminado[r > 16][alfa[r > 16] > 0].all()
