"""Validación estructural sin exponer valores de respuestas."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from tamizaje.normalization import normalize_text


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    row_number: int | None = None


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> ValidationResult:
    """Valida encabezados y anchura de filas usando mensajes no sensibles."""
    if not headers:
        return ValidationResult(
            errors=(ValidationIssue("empty_file", "El archivo no contiene columnas."),)
        )

    normalized_headers = [normalize_text(header) for header in headers]
    errors: list[ValidationIssue] = []

    if any(not header for header in normalized_headers):
        errors.append(
            ValidationIssue("empty_header", "Existe al menos un encabezado vacío.")
        )

    counts = Counter(header for header in normalized_headers if header)
    if any(count > 1 for count in counts.values()):
        errors.append(
            ValidationIssue(
                "duplicate_header",
                "Existen encabezados duplicados después de normalizarlos.",
            )
        )

    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(headers):
            errors.append(
                ValidationIssue(
                    "irregular_row",
                    "La fila tiene una cantidad de columnas distinta al encabezado.",
                    row_number=row_number,
                )
            )

    return ValidationResult(errors=tuple(errors))
