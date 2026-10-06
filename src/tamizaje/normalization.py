"""Normalización determinista de encabezados y respuestas."""

import unicodedata


def normalize_text(value: str) -> str:
    """Normaliza Unicode, saltos de línea y espacios exteriores."""
    normalized_lines = value.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", normalized_lines).strip()
