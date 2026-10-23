def test_qt_corre_sin_pantalla(qapp):
    assert qapp.platformName() == "offscreen"
