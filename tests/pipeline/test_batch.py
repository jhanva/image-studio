import csv
import threading

from image_studio.core.export import ExportSettings
from image_studio.pipeline.batch import list_images, run_batch
from image_studio.pipeline.settings import PRESETS

AJUSTES = PRESETS["producto"]


def _leer_informe(carpeta):
    with open(carpeta / "informe.csv", encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def test_archivo_corrupto_no_detiene_el_lote(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada", tmp_path / "salida"
    for nombre in ("a.png", "b.png", "c.png"):
        escribir_png(entrada / nombre)
    (entrada / "roto.png").write_bytes(b"no es una imagen")
    items = run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert [item.estado for item in items] == ["ok", "ok", "ok", "error"]
    filas = _leer_informe(salida)
    assert len(filas) == 4
    assert filas[3]["archivo"] == "roto.png" and filas[3]["estado"] == "error"
    assert (salida / "a.png").exists()


def test_nombres_repetidos_no_se_pisan(tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    escribir_png(entrada / "a.png")
    escribir_png(entrada / "a.jpg")
    items = run_batch(entrada, tmp_path / "salida", removedor_falso, AJUSTES, ExportSettings())
    salidas = {item.salida.name for item in items}
    assert salidas == {"a.png", "a_png.png"}


def test_cancelar_detiene_el_lote(tmp_path, escribir_png, removedor_falso):
    entrada = tmp_path / "entrada"
    for i in range(5):
        escribir_png(entrada / f"{i}.png")
    cancelar = threading.Event()
    items = run_batch(
        entrada,
        tmp_path / "salida",
        removedor_falso,
        AJUSTES,
        ExportSettings(),
        progreso=lambda hechos, total, item: cancelar.set(),
        cancelar=cancelar,
    )
    assert len(items) == 1


def test_cien_imagenes_sin_intervencion(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada", tmp_path / "salida"
    for i in range(100):
        escribir_png(entrada / f"img_{i:03d}.png")
    items = run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert len(items) == 100 and all(item.estado == "ok" for item in items)
    assert len(_leer_informe(salida)) == 100


def test_nombres_con_tildes(tmp_path, escribir_png, removedor_falso):
    entrada, salida = tmp_path / "entrada ñ", tmp_path / "salida ñ"
    escribir_png(entrada / "canción.png")
    run_batch(entrada, salida, removedor_falso, AJUSTES, ExportSettings())
    assert (salida / "canción.png").exists()
    assert _leer_informe(salida)[0]["archivo"] == "canción.png"


def test_lista_solo_imagenes(tmp_path, escribir_png):
    escribir_png(tmp_path / "a.png")
    (tmp_path / "informe.csv").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    assert [p.name for p in list_images(tmp_path)] == ["a.png"]
