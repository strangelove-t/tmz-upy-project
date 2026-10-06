"""Extracción segura de un borrador desde el encabezado de un CSV."""

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from tamizaje.importers import ALLOWED_DELIMITERS, ImportErrorSafe, detect_encoding
from tamizaje.normalization import normalize_text

DRAFT_COLUMNS = (
    "SourceColumnIndex",
    "SourceHeader",
    "NormalizedHeader",
    "QuestionCode",
    "FormsNumber",
    "QuestionType",
    "Required",
    "IsSensitive",
    "QuestionnaireVersion",
    "MappingStatus",
    "ReviewNotes",
)


@dataclass(frozen=True)
class QuestionnaireDraftRow:
    source_column_index: int
    source_header: str
    normalized_header: str
    question_code: str = ""
    forms_number: str = ""
    question_type: str = ""
    required: str = ""
    is_sensitive: str = ""
    questionnaire_version: str = ""
    mapping_status: str = "pending_review"
    review_notes: str = ""


@dataclass(frozen=True)
class QuestionnaireDraft:
    filename: str
    encoding: str
    delimiter: str
    rows: tuple[QuestionnaireDraftRow, ...] = field(repr=False)


def _first_csv_record(text: str) -> str:
    in_quotes = False
    index = 0
    while index < len(text):
        character = text[index]
        if character == '"':
            if in_quotes and index + 1 < len(text) and text[index + 1] == '"':
                index += 2
                continue
            in_quotes = not in_quotes
        elif character in "\r\n" and not in_quotes:
            return text[:index]
        index += 1
    return text


def _count_unquoted(record: str, delimiter: str) -> int:
    count = 0
    in_quotes = False
    index = 0
    while index < len(record):
        character = record[index]
        if character == '"':
            if in_quotes and index + 1 < len(record) and record[index + 1] == '"':
                index += 2
                continue
            in_quotes = not in_quotes
        elif character == delimiter and not in_quotes:
            count += 1
        index += 1
    return count


def _detect_header_delimiter(record: str) -> str:
    counts = sorted(
        (
            (_count_unquoted(record, delimiter), delimiter)
            for delimiter in ALLOWED_DELIMITERS
        ),
        reverse=True,
    )
    if not counts or counts[0][0] == 0:
        raise ImportErrorSafe("No fue posible identificar el separador del encabezado.")
    if len(counts) > 1 and counts[0][0] == counts[1][0]:
        raise ImportErrorSafe("El separador del encabezado es ambiguo.")
    return counts[0][1]


def build_questionnaire_draft(filename: str, content: bytes) -> QuestionnaireDraft:
    encoding = detect_encoding(content)
    header_record = _first_csv_record(content.decode(encoding))
    delimiter = _detect_header_delimiter(header_record)
    headers = next(csv.reader(io.StringIO(header_record), delimiter=delimiter), [])
    if not headers:
        raise ImportErrorSafe("El CSV no contiene encabezados.")

    rows = tuple(
        QuestionnaireDraftRow(
            source_column_index=index,
            source_header=header,
            normalized_header=normalize_text(header),
        )
        for index, header in enumerate(headers, start=1)
    )
    return QuestionnaireDraft(
        filename=Path(filename).name,
        encoding=encoding,
        delimiter=delimiter,
        rows=rows,
    )


def write_questionnaire_draft(draft: QuestionnaireDraft, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DRAFT_COLUMNS)
        writer.writeheader()
        for row in draft.rows:
            writer.writerow(
                {
                    "SourceColumnIndex": row.source_column_index,
                    "SourceHeader": row.source_header,
                    "NormalizedHeader": row.normalized_header,
                    "QuestionCode": row.question_code,
                    "FormsNumber": row.forms_number,
                    "QuestionType": row.question_type,
                    "Required": row.required,
                    "IsSensitive": row.is_sensitive,
                    "QuestionnaireVersion": row.questionnaire_version,
                    "MappingStatus": row.mapping_status,
                    "ReviewNotes": row.review_notes,
                }
            )


def read_pending_headers(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != DRAFT_COLUMNS:
            raise ImportErrorSafe("El borrador no cumple el contrato requerido.")
        return tuple(
            normalize_text(row["NormalizedHeader"])
            for row in reader
            if row["MappingStatus"] == "pending_review"
        )
