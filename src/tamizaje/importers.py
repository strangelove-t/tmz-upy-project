"""Previsualización segura de exportaciones CSV de Microsoft Forms."""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path

from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import (
    HeaderMappingResult,
    QuestionAlias,
    QuestionDefinition,
    compare_headers,
)
from tamizaje.validation import ValidationResult, validate_table

ALLOWED_DELIMITERS = ",;\t|"


class ImportErrorSafe(ValueError):
    """Error de importación cuyo mensaje no contiene contenido del archivo."""


@dataclass(frozen=True)
class CsvPreview:
    filename: str
    sha256: str
    encoding: str
    delimiter: str
    row_count: int
    total_row_count: int | None
    column_count: int
    is_limited: bool
    validation: ValidationResult
    headers_raw: tuple[str, ...] = field(repr=False)
    headers_normalized: tuple[str, ...] = field(repr=False)
    source_row_numbers: tuple[int, ...]
    rows_raw: tuple[tuple[str, ...], ...] = field(repr=False)
    rows_normalized: tuple[tuple[str, ...], ...] = field(repr=False)
    mapping: HeaderMappingResult | None = field(default=None, repr=False)

    def summary(self) -> dict[str, str | int | bool | None]:
        """Devuelve únicamente metadatos aptos para la interfaz y logs."""
        return {
            "filename": self.filename,
            "sha256_short": self.sha256[:12],
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "row_count": self.row_count,
            "total_row_count": self.total_row_count,
            "column_count": self.column_count,
            "is_limited": self.is_limited,
            "error_count": len(self.validation.errors),
            "warning_count": len(self.validation.warnings),
        }


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def detect_encoding(content: bytes) -> str:
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return "cp1252"
    return "utf-8"


def detect_delimiter(text: str) -> str:
    if not text:
        return ""

    candidates: list[tuple[tuple[int, int, int], str]] = []
    for delimiter in ALLOWED_DELIMITERS:
        try:
            rows = list(islice(csv.reader(io.StringIO(text), delimiter=delimiter), 10))
        except csv.Error:
            continue
        if not rows or len(rows[0]) < 2:
            continue

        header_width = len(rows[0])
        matching_rows = sum(len(row) == header_width for row in rows[1:])
        mismatched_rows = len(rows) - 1 - matching_rows
        candidates.append(
            ((matching_rows, -mismatched_rows, header_width), delimiter)
        )

    if not candidates:
        raise ImportErrorSafe("No fue posible identificar el separador del CSV.")

    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ImportErrorSafe("El separador del CSV es ambiguo.")
    return candidates[0][1]


def preview_csv(
    filename: str,
    content: bytes,
    *,
    max_rows: int | None = None,
    skip_rows: int = 0,
    questionnaire: tuple[QuestionDefinition, ...] | None = None,
    pending_headers: tuple[str, ...] = (),
    aliases: tuple[QuestionAlias, ...] = (),
) -> CsvPreview:
    """Analiza un CSV en memoria sin exponer respuestas en el resultado público."""
    if max_rows is not None and max_rows < 0:
        raise ValueError("max_rows no puede ser negativo")
    if skip_rows < 0:
        raise ValueError("skip_rows no puede ser negativo")

    encoding = detect_encoding(content)
    text = content.decode(encoding)
    delimiter = detect_delimiter(text)

    if not text:
        headers: list[str] = []
        rows: list[list[str]] = []
    else:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        headers = next(reader, [])
        rows = []
        source_row_numbers = []
        for source_row_number, row in enumerate(reader, start=2):
            if source_row_number < 2 + skip_rows:
                continue
            if max_rows is not None and len(rows) >= max_rows:
                break
            rows.append(row)
            source_row_numbers.append(source_row_number)

    if not text:
        source_row_numbers = []

    validation = validate_table(headers, rows)
    normalized_headers = tuple(normalize_text(value) for value in headers)
    normalized_rows = tuple(
        tuple(normalize_text(value) for value in row) for row in rows
    )
    limited = max_rows is not None
    mapping = (
        compare_headers(tuple(headers), questionnaire, pending_headers, aliases)
        if questionnaire is not None
        else None
    )

    return CsvPreview(
        filename=Path(filename).name,
        sha256=sha256_bytes(content),
        encoding=encoding,
        delimiter=delimiter,
        row_count=len(rows),
        total_row_count=None if limited else len(rows),
        column_count=len(headers),
        is_limited=limited,
        validation=validation,
        mapping=mapping,
        headers_raw=tuple(headers),
        headers_normalized=normalized_headers,
        source_row_numbers=tuple(source_row_numbers),
        rows_raw=tuple(tuple(value for value in row) for row in rows),
        rows_normalized=normalized_rows,
    )
