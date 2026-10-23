"""Diálogo para crear un preset propio a partir de otro."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from image_studio.pipeline.settings import MODELOS_SEGMENTACION, PipelineSettings


class PresetDialog(QDialog):
    def __init__(self, base: PipelineSettings, reservados: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guardar preset")
        self._reservados = reservados
        self.edit_nombre = QLineEdit()
        self.combo_modelo = QComboBox()
        self.combo_modelo.addItems(list(MODELOS_SEGMENTACION))
        self.combo_modelo.setCurrentText(base.modelo)
        self.check_matting = QCheckBox("Matting de borde")
        self.check_matting.setChecked(base.matting)
        self.check_limpieza = QCheckBox("Limpieza de color")
        self.check_limpieza.setChecked(base.limpieza_color)
        self.spin_banda = QSpinBox()
        self.spin_banda.setRange(1, 100)
        self.spin_banda.setSuffix(" px")
        self.spin_banda.setValue(base.banda_px)
        self.spin_desplazamiento = QSpinBox()
        self.spin_desplazamiento.setRange(-50, 50)
        self.spin_desplazamiento.setSuffix(" px")
        self.spin_desplazamiento.setValue(base.desplazamiento_px)
        self.spin_suavizado = QDoubleSpinBox()
        self.spin_suavizado.setRange(0.0, 20.0)
        self.spin_suavizado.setSingleStep(0.5)
        self.spin_suavizado.setSuffix(" px")
        self.spin_suavizado.setValue(base.suavizado_px)
        self.error = QLabel("")

        formulario = QFormLayout()
        formulario.addRow("Nombre", self.edit_nombre)
        formulario.addRow("Modelo", self.combo_modelo)
        formulario.addRow("", self.check_matting)
        formulario.addRow("", self.check_limpieza)
        formulario.addRow("Banda de matting", self.spin_banda)
        formulario.addRow("Desplazar borde", self.spin_desplazamiento)
        formulario.addRow("Suavizar borde", self.spin_suavizado)
        self.botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self.error)
        diseno.addWidget(self.botones)
        self.edit_nombre.textChanged.connect(self._validar)
        self._validar()

    def valor(self) -> tuple[str, PipelineSettings]:
        return self.edit_nombre.text().strip(), PipelineSettings(
            modelo=self.combo_modelo.currentText(),
            matting=self.check_matting.isChecked(),
            limpieza_color=self.check_limpieza.isChecked(),
            banda_px=self.spin_banda.value(),
            desplazamiento_px=self.spin_desplazamiento.value(),
            suavizado_px=self.spin_suavizado.value(),
        )

    def _validar(self, *_) -> None:
        nombre = self.edit_nombre.text().strip()
        mensaje = ""
        if nombre in self._reservados:
            mensaje = f"'{nombre}' es un preset incluido; usa otro nombre."
        self.error.setText(mensaje)
        valido = bool(nombre) and not mensaje
        self.botones.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valido)
