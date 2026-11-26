"""Presets de la herramienta de semitonos en %APPDATA%\\ImageStudio\\halftone_presets.json."""

from __future__ import annotations

from image_studio.core.halftone.settings import HalftoneSettings, KnockoutMode
from image_studio.pipeline.presets_store import PresetStore

HALFTONE_PRESETS: dict[str, HalftoneSettings] = {
    "Camiseta negra": HalftoneSettings(knockout=KnockoutMode.NEGRO),
    "Camiseta blanca": HalftoneSettings(knockout=KnockoutMode.BLANCO),
}


class HalftonePresetStore(PresetStore):
    ARCHIVO = "halftone_presets.json"
    INCLUIDOS = HALFTONE_PRESETS
    TIPO = HalftoneSettings
