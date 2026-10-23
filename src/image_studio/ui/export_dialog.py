"""Diálogo de exportación: formato, fondo, color, recorte, margen y DPI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from image_studio.core.export import FORMATOS_SALIDA, ExportSettings, Fondo


class ExportDialog(QDialog):
    def __init__(self, ajustes: ExportSettings | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar")
        ajustes = ajustes or ExportSettings()
        self._color = ajustes.color

        self.combo_formato = QComboBox()
        self.combo_formato.addItems(list(FORMATOS_SALIDA))
        self.combo_formato.setCurrentText(ajustes.formato)
        self.combo_fondo = QComboBox()
        self.combo_fondo.addItems([f.value for f in Fondo])
        self.combo_fondo.setCurrentText(ajustes.fondo.value)
        self.boton_color = QPushButton()
        self.boton_color.clicked.connect(self._elegir_color)
        self.check_recortar = QCheckBox("Recortar al contenido")
        self.check_recortar.setChecked(ajustes.recortar)
        self.spin_margen = QSpinBox()
        self.spin_margen.setRange(0, 2000)
        self.spin_margen.setSuffix(" px")
        self.spin_margen.setValue(ajustes.margen_px)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(0, 2400)
        self.spin_dpi.setSpecialValueText("Sin cambiar")
        self.spin_dpi.setValue(ajustes.dpi or 0)
        self.aviso = QLabel("JPG no admite transparencia: se exporta con fondo blanco.")
        self.aviso.setWordWrap(True)

        formulario = QFormLayout()
        formulario.addRow("Formato", self.combo_formato)
        formulario.addRow("Fondo", self.combo_fondo)
        formulario.addRow("Color", self.boton_color)
        formulario.addRow("", self.check_recortar)
        formulario.addRow("Margen", self.spin_margen)
        formulario.addRow("DPI", self.spin_dpi)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self.aviso)
        diseno.addWidget(botones)

        for senal in (self.combo_formato.currentTextChanged, self.combo_fondo.currentTextChanged):
            senal.connect(self._actualizar)
        self.check_recortar.toggled.connect(self._actualizar)
        self._actualizar()

    def ajustes(self) -> ExportSettings:
        return ExportSettings(
            formato=self.combo_formato.currentText(),
            fondo=Fondo(self.combo_fondo.currentText()),
            color=self._color,
            recortar=self.check_recortar.isChecked(),
            margen_px=self.spin_margen.value(),
            dpi=self.spin_dpi.value() or None,
        )

    def set_color(self, color: tuple[int, int, int]) -> None:
        self._color = tuple(color)
        self._actualizar()

    def _elegir_color(self) -> None:
        elegido = QColorDialog.getColor(QColor(*self._color), self, "Color de fondo")
        if elegido.isValid():
            self.set_color((elegido.red(), elegido.green(), elegido.blue()))

    def _actualizar(self, *_) -> None:
        r, g, b = self._color
        self.boton_color.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.boton_color.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
        self.boton_color.setEnabled(self.combo_fondo.currentText() == Fondo.COLOR.value)
        self.spin_margen.setEnabled(self.check_recortar.isChecked())
        transparente_en_jpg = (
            self.combo_formato.currentText() == "jpg"
            and self.combo_fondo.currentText() == Fondo.TRANSPARENTE.value
        )
        self.aviso.setHidden(not transparente_en_jpg)
