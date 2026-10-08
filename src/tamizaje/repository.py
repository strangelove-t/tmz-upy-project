"""Consultas de lectura para las vistas; no modifican la base."""

import sqlite3
from decimal import Decimal

import pandas as pd

from tamizaje.models import EngineConfig
from tamizaje.triage import TriageComponents, explain_priority, triage_key


def last_import(connection: sqlite3.Connection) -> dict | None:
    row = connection.execute(
        "SELECT filename, imported_at, questionnaire_version, scoring_version, "
        "row_count FROM imports ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    keys = ("filename", "imported_at", "questionnaire_version", "scoring_version")
    return dict(zip((*keys, "row_count"), row, strict=True))


def area_results_frame(
    connection: sqlite3.Connection, engine: EngineConfig
) -> pd.DataFrame:
    """Resultados de la versión activa para envíos vigentes."""
    frame = pd.read_sql_query(
        """
        SELECT su.id AS submission_id, st.student_name, st.career,
               st.group_name, ar.area_code, ar.normalized_score,
               ar.traffic_light, ar.is_complete, ar.recommendation_code
        FROM area_results ar
        JOIN submissions su ON su.id = ar.submission_id
        JOIN students st ON st.id = su.student_id
        WHERE su.is_current = 1 AND ar.scoring_version = ?
        """,
        connection,
        params=(engine.scoring.version,),
    )
    names = {area.area_code: area.area_name for area in engine.scoring.areas}
    frame["area_name"] = frame["area_code"].map(names)
    frame["normalized_score"] = pd.to_numeric(frame["normalized_score"])
    frame["traffic_light"] = frame["traffic_light"].fillna("Incompleta")
    return frame


def cases_frame(
    connection: sqlite3.Connection, engine: EngineConfig, current_only: bool = True
) -> pd.DataFrame:
    """Casos con sus componentes de triage, ordenados por prioridad."""
    frame = pd.read_sql_query(
        f"""
        SELECT c.id AS case_id, c.submission_id, st.student_name,
               st.student_upn, st.career, st.group_name, c.case_level,
               c.case_level_rank, c.case_source, c.requested_contact,
               c.case_status, c.contact_status, c.assigned_to,
               c.lowest_area_score, c.critical_area_code,
               c.priority_alert_count, c.total_alert_count, c.detected_at,
               c.next_follow_up_at, c.initial_reason,
               (SELECT GROUP_CONCAT(DISTINCT a.alert_category)
                  FROM alerts a
                 WHERE a.submission_id = c.submission_id
                   AND a.rule_version = c.rule_version) AS categories
        FROM cases c
        JOIN submissions su ON su.id = c.submission_id
        JOIN students st ON st.id = su.student_id
        {"WHERE su.is_current = 1" if current_only else ""}
        """,
        connection,
    )
    if frame.empty:
        frame["priority"] = []
        frame["priority_reason"] = []
        return frame

    components = [
        TriageComponents(
            requested_contact=bool(row.requested_contact),
            case_level_rank=int(row.case_level_rank),
            lowest_area_score=(
                Decimal(row.lowest_area_score)
                if row.lowest_area_score is not None
                else None
            ),
            priority_alert_count=int(row.priority_alert_count),
            total_alert_count=int(row.total_alert_count),
            detected_at=row.detected_at,
        )
        for row in frame.itertuples()
    ]
    frame["priority_reason"] = [
        explain_priority(component, level)
        for component, level in zip(components, frame["case_level"], strict=True)
    ]
    order = sorted(range(len(components)), key=lambda i: triage_key(components[i]))
    frame = frame.iloc[order].reset_index(drop=True)
    frame.insert(0, "priority", range(1, len(frame) + 1))
    frame["lowest_area_score"] = pd.to_numeric(frame["lowest_area_score"])
    frame["requested_contact"] = frame["requested_contact"].astype(bool)
    frame["categories"] = frame["categories"].fillna("")
    return frame


def students_frame(connection: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT su.id AS submission_id, st.id AS student_id, st.student_name,
               st.student_upn, st.career, st.group_name, su.submitted_at,
               su.is_current, su.duplicate_student_submission
        FROM submissions su JOIN students st ON st.id = su.student_id
        ORDER BY st.student_name, su.id
        """,
        connection,
    )


def submission_alerts(
    connection: sqlite3.Connection, submission_id: int, rule_version: str
) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT rule_code, question_code, trigger_response, alert_level,
               alert_category, alert_reason, suggested_action
        FROM alerts WHERE submission_id = ? AND rule_version = ?
        ORDER BY id
        """,
        connection,
        params=(submission_id, rule_version),
    )


def submission_responses(
    connection: sqlite3.Connection,
    submission_id: int,
    question_texts: dict[str, str],
) -> pd.DataFrame:
    frame = pd.read_sql_query(
        "SELECT question_code, response_raw, is_sensitive FROM responses "
        "WHERE submission_id = ? ORDER BY question_code",
        connection,
        params=(submission_id,),
    )
    frame.insert(1, "question_text", frame["question_code"].map(question_texts))
    frame["is_sensitive"] = frame["is_sensitive"].astype(bool)
    return frame


def submission_case(
    connection: sqlite3.Connection, submission_id: int
) -> dict | None:
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM cases WHERE submission_id = ?", (submission_id,)
        ).fetchone()
    finally:
        connection.row_factory = None
    return dict(row) if row is not None else None


def case_notes(connection: sqlite3.Connection, case_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT created_at, author, note FROM case_notes WHERE case_id = ? "
        "ORDER BY id DESC",
        connection,
        params=(case_id,),
    )
