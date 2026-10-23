from image_studio.engines.hardware import Hardware, detect_hardware, parse_nvidia_smi


def test_lee_la_primera_gpu():
    assert parse_nvidia_smi("NVIDIA GeForce RTX 3050, 8192\n") == ("NVIDIA GeForce RTX 3050", 8192)
    assert parse_nvidia_smi("Quadro P1000, rev 2, 4096\nOtra, 2048\n") == ("Quadro P1000, rev 2", 4096)


def test_sin_nvidia():
    assert parse_nvidia_smi("") == (None, 0)
    assert parse_nvidia_smi("error inesperado") == (None, 0)


def test_detecta_con_consulta_inyectada():
    equipo = detect_hardware(consultar=lambda: "NVIDIA GeForce RTX 3050, 8192")
    assert equipo.gpu == "NVIDIA GeForce RTX 3050" and equipo.vram_mb == 8192
    assert equipo.tiene_nvidia and equipo.ram_mb > 0 and equipo.cpus >= 1


def test_descripciones():
    assert Hardware("RTX 3050", 8192, 16384, 6).describir() == "RTX 3050 (8 GB), 16 GB de RAM"
    assert Hardware(None, 0, 8192, 4).describir() == "Sin GPU NVIDIA, 8 GB de RAM, 4 núcleos"
