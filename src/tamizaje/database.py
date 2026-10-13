"""Persistencia transaccional y auditable en SQLite."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tamizaje import SCORING_VERSION
from tamizaje.alerts import AlertConfig, TriggeredAlert, evaluate_alerts
from tamizaje.cases import CASE_STATUSES, CONTACT_STATUSES, consolidate_case
from tamizaje.importers import CsvPreview
from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import QuestionDefinition
from tamizaje.recommendations import Recommendation, recommendation_for
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

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER NOT NULL
                REFERENCES submissions(id) ON DELETE CASCADE,
            rule_code TEXT NOT NULL,
            question_code TEXT NOT NULL,
            trigger_response TEXT NOT NULL,
            alert_level TEXT NOT NULL,
            alert_category TEXT NOT NULL,
            alert_reason TEXT NOT NULL,
            suggested_action TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            UNIQUE(submission_id, rule_code, rule_version)
        );

        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER NOT NULL UNIQUE
                REFERENCES submissions(id) ON DELETE CASCADE,
            case_level TEXT NOT NULL,
            case_level_rank INTEGER NOT NULL,
            case_source TEXT NOT NULL,
            requested_contact INTEGER NOT NULL CHECK (requested_contact IN (0, 1)),
            case_status TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            assigned_to TEXT,
            initial_reason TEXT NOT NULL,
            contact_status TEXT NOT NULL,
            first_contact_at TEXT,
            last_contact_at TEXT,
            next_follow_up_at TEXT,
            referral_destination TEXT,
            closed_at TEXT,
            closure_reason TEXT,
            resolution_notes TEXT,
            lowest_area_score TEXT,
            critical_area_code TEXT,
            priority_alert_count INTEGER NOT NULL,
            total_alert_count INTEGER NOT NULL,
            scoring_version TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS case_notes (
            id INTEGER PRIMARY KEY,
            case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            author TEXT NOT NULL,
            note TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER NOT NULL
                REFERENCES submissions(id) ON DELETE CASCADE,
            export_type TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            file_path TEXT NOT NULL,
            template_version TEXT NOT NULL,
            includes_sensitive_summary INTEGER NOT NULL DEFAULT 0
                CHECK (includes_sensitive_summary IN (0, 1))
        );
        """
    )
    case_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(cases)").fetchall()
    }
    if "is_active" not in case_columns:
        connection.execute(
            "ALTER TABLE cases ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 "
            "CHECK (is_active IN (0, 1))"
        )
    export_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(exports)").fetchall()
    }
    if "includes_sensitive_summary" not in export_columns:
        connection.execute(
            "ALTER TABLE exports ADD COLUMN includes_sensitive_summary "
            "INTEGER NOT NULL DEFAULT 0 CHECK (includes_sensitive_summary IN (0, 1))"
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def is_imported(connection: sqlite3.Connection, sha256: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM imports WHERE sha256 = ? LIMIT 1", (sha256,)
    ).fetchone()
    return row is not None


def persist_area_results(
    connection: sqlite3.Connection,
    submission_id: int,
    results: tuple[AreaResult, ...],
    recommendations: tuple[Recommendation, ...] = (),
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
                (
                    recommendation.recommendation_code
                    if (recommendation := recommendation_for(result, recommendations))
                    else None
                ),
                result.scoring_version,
                ";".join(result.issues),
            )
            for result in results
        ),
    )


def persist_alerts(
    connection: sqlite3.Connection,
    submission_id: int,
    alerts: tuple[TriggeredAlert, ...],
    rule_version: str,
    detected_at: str,
) -> None:
    """Reemplaza sólo las alertas de la versión de reglas evaluada."""
    connection.execute(
        "DELETE FROM alerts WHERE submission_id = ? AND rule_version = ?",
        (submission_id, rule_version),
    )
    connection.executemany(
        """
        INSERT INTO alerts (
            submission_id, rule_code, question_code, trigger_response,
            alert_level, alert_category, alert_reason, suggested_action,
            detected_at, rule_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                submission_id,
                alert.rule_code,
                alert.question_code,
                alert.trigger_response,
                alert.alert_level,
                alert.alert_category,
                alert.alert_reason,
                alert.suggested_action,
                detected_at,
                alert.rule_version,
            )
            for alert in alerts
        ),
    )


def process_submission(
    connection: sqlite3.Connection,
    submission_id: int,
    responses: dict[str, str],
    scoring_config: ScoringConfig,
    alert_config: AlertConfig | None = None,
    recommendations: tuple[Recommendation, ...] = (),
    detected_at: str | None = None,
) -> None:
    """Calcula áreas, alertas y caso de un envío en la transacción activa.

    El seguimiento humano de un caso existente (estado, contacto, notas) nunca
    se sobrescribe; sólo se actualizan sus componentes calculados.
    """
    detected_at = detected_at or _now()
    area_results = score_responses(responses, scoring_config)
    persist_area_results(connection, submission_id, area_results, recommendations)
    if alert_config is None:
        return

    alerts = evaluate_alerts(responses, alert_config)
    persist_alerts(
        connection, submission_id, alerts, alert_config.version, detected_at
    )
    case = consolidate_case(alerts, area_results, alert_config)
    if case is None:
        connection.execute(
            "UPDATE cases SET is_active = 0 WHERE submission_id = ?",
            (submission_id,),
        )
        return
    computed = (
        case.case_level,
        case.case_level_rank,
        case.case_source,
        int(case.requested_contact),
        case.initial_reason,
        str(case.lowest_area_score) if case.lowest_area_score is not None else None,
        case.critical_area_code,
        case.priority_alert_count,
        case.total_alert_count,
        scoring_config.version,
        alert_config.version,
    )
    existing = connection.execute(
        "SELECT id FROM cases WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    if existing is None:
        connection.execute(
            """
            INSERT INTO cases (
                case_level, case_level_rank, case_source, requested_contact,
                initial_reason, lowest_area_score, critical_area_code,
                priority_alert_count, total_alert_count, scoring_version,
                rule_version, submission_id, case_status, opened_at,
                detected_at, contact_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *computed,
                submission_id,
                CASE_STATUSES[0],
                detected_at,
                detected_at,
                CONTACT_STATUSES[0],
            ),
        )
    else:
        connection.execute(
            """
            UPDATE cases SET
                case_level = ?, case_level_rank = ?, case_source = ?,
                requested_contact = ?, initial_reason = ?, lowest_area_score = ?,
                critical_area_code = ?, priority_alert_count = ?,
                total_alert_count = ?, scoring_version = ?, rule_version = ?,
                is_active = 1
            WHERE id = ?
            """,
            (*computed, existing[0]),
        )


def stored_responses(
    connection: sqlite3.Connection, submission_id: int
) -> dict[str, str]:
    return dict(
        connection.execute(
            "SELECT question_code, response_raw FROM responses "
            "WHERE submission_id = ?",
            (submission_id,),
        ).fetchall()
    )


def recalculate_all(
    connection: sqlite3.Connection,
    scoring_config: ScoringConfig,
    alert_config: AlertConfig,
    recommendations: tuple[Recommendation, ...] = (),
) -> int:
    """Aplica las versiones activas a los envíos históricos sin reimportar.

    Los resultados de otras versiones permanecen intactos. Todo el lote se
    revierte si cualquier envío falla.
    """
    with connection:
        submission_ids = [
            row[0]
            for row in connection.execute("SELECT id FROM submissions ORDER BY id")
        ]
        for submission_id in submission_ids:
            detected = connection.execute(
                "SELECT detected_at FROM cases WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            process_submission(
                connection,
                submission_id,
                stored_responses(connection, submission_id),
                scoring_config,
                alert_config,
                recommendations,
                detected_at=detected[0] if detected else None,
            )
    return len(submission_ids)


CASE_EDITABLE_FIELDS = {
    "case_status",
    "assigned_to",
    "contact_status",
    "next_follow_up_at",
    "referral_destination",
    "closure_reason",
    "resolution_notes",
}


def update_case(
    connection: sqlite3.Connection, case_id: int, **fields: str | None
) -> None:
    """Actualiza sólo campos de seguimiento; los componentes calculados no."""
    unknown = set(fields) - CASE_EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Campos no editables: {sorted(unknown)}")
    if "case_status" in fields and fields["case_status"] not in CASE_STATUSES:
        raise ValueError("Estado de caso inválido.")
    if "contact_status" in fields and fields["contact_status"] not in CONTACT_STATUSES:
        raise ValueError("Estado de contacto inválido.")

    now = _now()
    with connection:
        current = connection.execute(
            "SELECT case_status, contact_status, first_contact_at "
            "FROM cases WHERE id = ?",
            (case_id,),
        ).fetchone()
        if current is None:
            raise ValueError("El caso no existe.")
        updates = dict(fields)
        new_contact = fields.get("contact_status")
        if new_contact and new_contact != CONTACT_STATUSES[0]:
            if new_contact != current[1]:
                updates["last_contact_at"] = now
            if current[2] is None:
                updates["first_contact_at"] = now
        if fields.get("case_status") == "Cerrado" and current[0] != "Cerrado":
            updates["closed_at"] = now
        elif "case_status" in fields and fields["case_status"] != "Cerrado":
            updates["closed_at"] = None
        if updates:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            connection.execute(
                f"UPDATE cases SET {assignments} WHERE id = ?",
                (*updates.values(), case_id),
            )


def add_case_note(
    connection: sqlite3.Connection, case_id: int, author: str, note: str
) -> None:
    author, note = normalize_text(author), normalize_text(note)
    if not author or not note:
        raise ValueError("La nota requiere autor y contenido.")
    with connection:
        connection.execute(
            "INSERT INTO case_notes (case_id, created_at, author, note) "
            "VALUES (?, ?, ?, ?)",
            (case_id, _now(), author, note),
        )


def set_current_submission(connection: sqlite3.Connection, submission_id: int) -> None:
    """Resuelve manualmente cuál envío de un alumno es el vigente."""
    with connection:
        row = connection.execute(
            "SELECT student_id FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise ValueError("El envío no existe.")
        connection.execute(
            "UPDATE submissions SET is_current = (id = ?) WHERE student_id = ?",
            (submission_id, row[0]),
        )


def record_export(
    connection: sqlite3.Connection,
    submission_id: int,
    export_type: str,
    file_path: str,
    template_version: str,
    includes_sensitive_summary: bool = False,
) -> None:
    with connection:
        connection.execute(
            "INSERT INTO exports (submission_id, export_type, generated_at, "
            "file_path, template_version, includes_sensitive_summary) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                submission_id,
                export_type,
                _now(),
                file_path,
                template_version,
                int(includes_sensitive_summary),
            ),
        )


def import_preview(
    connection: sqlite3.Connection,
    preview: CsvPreview,
    questionnaire: tuple[QuestionDefinition, ...],
    scoring_config: ScoringConfig | None = None,
    alert_config: AlertConfig | None = None,
    recommendations: tuple[Recommendation, ...] = (),
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

    imported_at = _now()
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
                imported_at,
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
                process_submission(
                    connection,
                    submission_id,
                    raw_by_code,
                    scoring_config,
                    alert_config,
                    recommendations,
                    detected_at=imported_at,
                )

    return import_id
