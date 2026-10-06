"""Persistencia transaccional y auditable en SQLite."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tamizaje import SCORING_VERSION
from tamizaje.importers import CsvPreview
from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import QuestionDefinition
from tamizaje.scoring import AreaResult, score_responses
from tamizaje.scoring_config import ScoringConfig

SPECIALIZED_CODES = {
    "ADM_RESPONSE_ID",
    "ADM_STARTED_AT",
    "ADM_COMPLETED_AT",
    "ADM_EMAIL",
    "ADM_NAME",
    "DG02",
    "DG03",
}


class DuplicateImportError(ValueError):
    """El archivo ya fue importado."""


class InvalidPreviewError(ValueError):
    """La previsualización no es apta para persistirse."""


def connect_database(path: str | Path) -> sqlite3.Connection:
    database_path = Path(path)
    if str(path) != ":memory:":
        database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            imported_at TEXT NOT NULL,
            questionnaire_version TEXT NOT NULL,
            scoring_version TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            column_count INTEGER NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            student_upn TEXT NOT NULL,
            student_upn_normalized TEXT NOT NULL UNIQUE,
            student_name TEXT NOT NULL,
            career TEXT NOT NULL,
            group_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY,
            external_response_id TEXT NOT NULL UNIQUE,
            student_id INTEGER NOT NULL REFERENCES students(id),
            import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
            source_row_number INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
            duplicate_student_submission INTEGER NOT NULL
                CHECK (duplicate_student_submission IN (0, 1)),
            UNIQUE(import_id, source_row_number)
        );

        CREATE TABLE IF NOT EXISTS responses (
            submission_id INTEGER NOT NULL
                REFERENCES submissions(id) ON DELETE CASCADE,
            question_code TEXT NOT NULL,
            response_raw TEXT NOT NULL,
            response_normalized TEXT NOT NULL,
            is_sensitive INTEGER NOT NULL CHECK (is_sensitive IN (0, 1)),
            PRIMARY KEY (submission_id, question_code)
        );

        CREATE TABLE IF NOT EXISTS area_results (
            submission_id INTEGER NOT NULL
                REFERENCES submissions(id) ON DELETE CASCADE,
            area_code TEXT NOT NULL,
            raw_average TEXT,
            normalized_score TEXT,
            traffic_light TEXT,
            valid_item_count INTEGER NOT NULL,
            applicable_item_count INTEGER NOT NULL,
            expected_item_count INTEGER NOT NULL,
            is_complete INTEGER NOT NULL CHECK (is_complete IN (0, 1)),
            recommendation_code TEXT,
            scoring_version TEXT NOT NULL,
            calculation_notes TEXT NOT NULL,
            PRIMARY KEY (submission_id, area_code, scoring_version)
        );
        """
    )


def is_imported(connection: sqlite3.Connection, sha256: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM imports WHERE sha256 = ? LIMIT 1", (sha256,)
    ).fetchone()
    return row is not None


def persist_area_results(
    connection: sqlite3.Connection,
    submission_id: int,
    results: tuple[AreaResult, ...],
) -> None:
    """Reemplaza únicamente la versión calculada dentro de la transacción activa."""
    versions = {result.scoring_version for result in results}
    for version in versions:
        connection.execute(
            "DELETE FROM area_results WHERE submission_id = ? AND scoring_version = ?",
            (submission_id, version),
        )
    connection.executemany(
        """
        INSERT INTO area_results (
            submission_id, area_code, raw_average, normalized_score,
            traffic_light, valid_item_count, applicable_item_count,
            expected_item_count, is_complete, recommendation_code,
            scoring_version, calculation_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                submission_id,
                result.area_code,
                str(result.raw_average) if result.raw_average is not None else None,
                (
                    str(result.normalized_score)
                    if result.normalized_score is not None
                    else None
                ),
                result.traffic_light,
                result.valid_item_count,
                result.applicable_item_count,
                result.expected_item_count,
                int(result.is_complete),
                None,
                result.scoring_version,
                ";".join(result.issues),
            )
            for result in results
        ),
    )


def import_preview(
    connection: sqlite3.Connection,
    preview: CsvPreview,
    questionnaire: tuple[QuestionDefinition, ...],
    scoring_config: ScoringConfig | None = None,
) -> int:
    mapping_invalid = preview.mapping is not None and not preview.mapping.is_valid
    if (
        preview.is_limited
        or not preview.validation.is_valid
        or mapping_invalid
        or preview.mapping is None
    ):
        raise InvalidPreviewError("La previsualización no puede importarse.")
    if is_imported(connection, preview.sha256):
        raise DuplicateImportError("El archivo ya fue importado.")

    column_by_code = {
        assignment.question_code: assignment.column_index - 1
        for assignment in preview.mapping.assignments
    }
    if not SPECIALIZED_CODES <= column_by_code.keys():
        raise InvalidPreviewError("Faltan campos especializados obligatorios.")

    question_by_code = {
        question.question_code: question
        for question in questionnaire
        if question.question_code is not None
    }
    questionnaire_versions = {
        question.questionnaire_version for question in questionnaire
    }
    if len(questionnaire_versions) != 1:
        raise InvalidPreviewError("La versión del cuestionario no es consistente.")
    questionnaire_version = questionnaire_versions.pop()

    response_id_index = column_by_code["ADM_RESPONSE_ID"]
    external_response_ids = [
        row[response_id_index] for row in preview.rows_normalized
    ]
    if len(external_response_ids) != len(set(external_response_ids)) or any(
        connection.execute(
            "SELECT 1 FROM submissions WHERE external_response_id = ? LIMIT 1",
            (external_response_id,),
        ).fetchone()
        is not None
        for external_response_id in external_response_ids
    ):
        raise DuplicateImportError("El envío ya fue importado.")

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO imports (
                filename, sha256, imported_at, questionnaire_version,
                scoring_version, row_count, column_count, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preview.filename,
                preview.sha256,
                datetime.now(UTC).isoformat(),
                questionnaire_version,
                scoring_config.version if scoring_config else SCORING_VERSION,
                preview.row_count,
                preview.column_count,
                "completed",
            ),
        )
        import_id = cursor.lastrowid
        if import_id is None:
            raise sqlite3.DatabaseError("No fue posible crear la importación.")

        for source_row_number, raw_row, normalized_row in zip(
            preview.source_row_numbers,
            preview.rows_raw,
            preview.rows_normalized,
            strict=True,
        ):
            raw_by_code = {
                code: raw_row[column_index]
                for code, column_index in column_by_code.items()
            }
            normalized_by_code = {
                code: normalized_row[column_index]
                for code, column_index in column_by_code.items()
            }
            if any(not normalized_by_code[code] for code in SPECIALIZED_CODES):
                raise InvalidPreviewError(
                    f"Falta un campo obligatorio en la fila {source_row_number}."
                )

            upn_normalized = normalize_text(raw_by_code["ADM_EMAIL"]).casefold()
            student_row = connection.execute(
                "SELECT id FROM students WHERE student_upn_normalized = ?",
                (upn_normalized,),
            ).fetchone()
            if student_row is None:
                student_cursor = connection.execute(
                    """
                    INSERT INTO students (
                        student_upn, student_upn_normalized, student_name,
                        career, group_name
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        raw_by_code["ADM_EMAIL"],
                        upn_normalized,
                        raw_by_code["ADM_NAME"],
                        raw_by_code["DG02"],
                        raw_by_code["DG03"],
                    ),
                )
                student_id = student_cursor.lastrowid
                if student_id is None:
                    raise sqlite3.DatabaseError("No fue posible crear el alumno.")
            else:
                student_id = student_row[0]

            has_previous_submission = connection.execute(
                "SELECT 1 FROM submissions WHERE student_id = ? LIMIT 1",
                (student_id,),
            ).fetchone() is not None
            submission_cursor = connection.execute(
                """
                INSERT INTO submissions (
                    external_response_id, student_id, import_id,
                    source_row_number, started_at, submitted_at, is_current,
                    duplicate_student_submission
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_by_code["ADM_RESPONSE_ID"],
                    student_id,
                    import_id,
                    source_row_number,
                    raw_by_code["ADM_STARTED_AT"],
                    raw_by_code["ADM_COMPLETED_AT"],
                    int(not has_previous_submission),
                    int(has_previous_submission),
                ),
            )
            submission_id = submission_cursor.lastrowid
            if submission_id is None:
                raise sqlite3.DatabaseError("No fue posible crear el envío.")

            connection.executemany(
                """
                INSERT INTO responses (
                    submission_id,
                    question_code,
                    response_raw,
                    response_normalized,
                    is_sensitive
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (
                        submission_id,
                        code,
                        raw_by_code[code],
                        normalized_by_code[code],
                        int(question_by_code[code].is_sensitive is True),
                    )
                    for code in column_by_code
                    if code not in SPECIALIZED_CODES
                ),
            )
            if scoring_config is not None:
                persist_area_results(
                    connection,
                    submission_id,
                    score_responses(raw_by_code, scoring_config),
                )

    return import_id
