from decimal import Decimal

import pytest
from test_import import synthetic_import_scoring_config, synthetic_mapped_preview

from tamizaje.alerts import AlertConfig, AlertRule, TriggeredAlert
from tamizaje.cases import (
    SOURCE_AUTOMATIC,
    SOURCE_STUDENT_REQUEST,
    consolidate_case,
)
from tamizaje.database import (
    add_case_note,
    connect_database,
    import_preview,
    initialize_database,
    recalculate_all,
    set_current_submission,
    update_case,
)
from tamizaje.scoring import AreaResult
from tamizaje.triage import TriageComponents, triage_key

LEVELS = ("Atención prioritaria", "Revisión manual", "Seguimiento preventivo")


def alert_config(*rules: AlertRule) -> AlertConfig:
    return AlertConfig(
        version="t1",
        levels=LEVELS,
        contact_request_category="Solicitud de contacto",
        rules=rules,
    )


def rule(code: str, question: str, response: str, level: str, category="Cat"):
    return AlertRule(
        code, question, "exact", response, level, category, f"Motivo {code}",
        "Acción", "t1",
    )


def triggered(level: str, category: str = "Cat", code: str = "R") -> TriggeredAlert:
    return TriggeredAlert(code, "Q", "x", level, category, f"Motivo {code}", "A", "t1")


def area(code: str, score: str | None) -> AreaResult:
    return AreaResult(
        code,
        None,
        Decimal(score) if score is not None else None,
        None,
        1,
        1,
        1,
        score is not None,
        "test",
    )


def test_no_alerts_creates_no_case() -> None:
    assert consolidate_case((), (area("A01", "10"),), alert_config()) is None


def test_case_level_follows_configured_severity_order() -> None:
    case = consolidate_case(
        (triggered(LEVELS[2], code="P"), triggered(LEVELS[1], code="M")),
        (),
        alert_config(),
    )

    assert case.case_level == "Revisión manual"
    assert case.case_level_rank == 2
    assert case.initial_reason == "Motivo M"
    assert case.case_source == SOURCE_AUTOMATIC
    assert case.priority_alert_count == 0
    assert case.total_alert_count == 2


def test_contact_request_sets_student_source() -> None:
    case = consolidate_case(
        (triggered(LEVELS[0], "Solicitud de contacto"),), (), alert_config()
    )

    assert case.case_source == SOURCE_STUDENT_REQUEST
    assert case.requested_contact is True
    assert case.priority_alert_count == 1


def test_lowest_area_ignores_incomplete_areas() -> None:
    case = consolidate_case(
        (triggered(LEVELS[2]),),
        (area("A01", "55"), area("A02", None), area("A03", "20")),
        alert_config(),
    )

    assert case.lowest_area_score == Decimal("20")
    assert case.critical_area_code == "A03"


def components(**overrides) -> TriageComponents:
    values = dict(
        requested_contact=False,
        case_level_rank=1,
        lowest_area_score=Decimal("50"),
        priority_alert_count=1,
        total_alert_count=1,
        detected_at="2026-01-01",
    )
    values.update(overrides)
    return TriageComponents(**values)


def test_triage_order_is_lexicographic() -> None:
    cases = {
        "contact": components(requested_contact=True, case_level_rank=3),
        "severe": components(),
        "lower_area": components(lowest_area_score=Decimal("10")),
        "more_priority": components(priority_alert_count=3),
        "more_total": components(total_alert_count=5),
        "older": components(detected_at="2025-12-01"),
        "no_area": components(lowest_area_score=None),
        "preventive": components(case_level_rank=3),
    }

    ordered = sorted(cases, key=lambda name: triage_key(cases[name]))

    assert ordered == [
        "contact",
        "lower_area",
        "more_priority",
        "more_total",
        "older",
        "severe",
        "no_area",
        "preventive",
    ]


def import_with_alerts(tmp_path, config: AlertConfig, **preview_kwargs):
    questionnaire, preview = synthetic_mapped_preview(**preview_kwargs)
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    import_preview(
        connection,
        preview,
        questionnaire,
        synthetic_import_scoring_config(),
        alert_config=config,
    )
    return connection


def test_import_creates_several_alerts_but_one_case(tmp_path) -> None:
    config = alert_config(
        rule("R1", "Q01", "Yes", LEVELS[2]),
        rule("R2", "Q02", "No", LEVELS[0], "Solicitud de contacto"),
    )
    connection = import_with_alerts(tmp_path, config)

    assert connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 2
    case = connection.execute(
        "SELECT case_level, case_source, case_status, total_alert_count, "
        "priority_alert_count, rule_version FROM cases"
    ).fetchall()
    assert case == [
        ("Atención prioritaria", SOURCE_STUDENT_REQUEST, "Nuevo", 2, 1, "t1")
    ]


def test_import_without_triggered_alerts_creates_no_case(tmp_path) -> None:
    connection = import_with_alerts(
        tmp_path, alert_config(rule("R1", "Q01", "No", LEVELS[0]))
    )

    assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0


def test_alert_failure_rolls_back_complete_import(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    connection.execute(
        "CREATE TRIGGER fail BEFORE INSERT ON cases "
        "BEGIN SELECT RAISE(ABORT, 'forced'); END"
    )

    with pytest.raises(Exception, match="forced"):
        import_preview(
            connection,
            preview,
            questionnaire,
            synthetic_import_scoring_config(),
            alert_config=alert_config(rule("R1", "Q01", "Yes", LEVELS[0])),
        )

    for table in ("imports", "submissions", "area_results", "alerts", "cases"):
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_recalculation_preserves_follow_up_and_is_idempotent(tmp_path) -> None:
    config = alert_config(rule("R1", "Q01", "Yes", LEVELS[2]))
    connection = import_with_alerts(tmp_path, config)
    case_id = connection.execute("SELECT id FROM cases").fetchone()[0]
    update_case(connection, case_id, case_status="En seguimiento", assigned_to="Ana")
    add_case_note(connection, case_id, "Ana", "Nota sintética")

    stricter = alert_config(
        rule("R1", "Q01", "Yes", LEVELS[0]), rule("R2", "Q02", "No", LEVELS[2])
    )
    assert recalculate_all(connection, synthetic_import_scoring_config(), stricter) == 1
    recalculate_all(connection, synthetic_import_scoring_config(), stricter)

    assert connection.execute(
        "SELECT case_level, case_status, assigned_to, total_alert_count FROM cases"
    ).fetchall() == [("Atención prioritaria", "En seguimiento", "Ana", 2)]
    assert connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM case_notes").fetchone()[0] == 1


def test_update_case_tracks_contact_and_closure(tmp_path) -> None:
    connection = import_with_alerts(
        tmp_path, alert_config(rule("R1", "Q01", "Yes", LEVELS[0]))
    )
    case_id = connection.execute("SELECT id FROM cases").fetchone()[0]

    update_case(connection, case_id, contact_status="Contactado")
    update_case(connection, case_id, case_status="Cerrado", closure_reason="Atendido")

    first, last, closed = connection.execute(
        "SELECT first_contact_at, last_contact_at, closed_at FROM cases"
    ).fetchone()
    assert first and last and closed

    update_case(connection, case_id, case_status="En seguimiento")
    assert connection.execute("SELECT closed_at FROM cases").fetchone()[0] is None


@pytest.mark.parametrize(
    "fields",
    [
        {"case_level": "Revisión manual"},
        {"case_status": "Inventado"},
        {"contact_status": "Inventado"},
    ],
)
def test_update_case_rejects_computed_or_invalid_fields(tmp_path, fields) -> None:
    connection = import_with_alerts(
        tmp_path, alert_config(rule("R1", "Q01", "Yes", LEVELS[0]))
    )
    case_id = connection.execute("SELECT id FROM cases").fetchone()[0]

    with pytest.raises(ValueError):
        update_case(connection, case_id, **fields)


def test_add_case_note_requires_content(tmp_path) -> None:
    connection = import_with_alerts(
        tmp_path, alert_config(rule("R1", "Q01", "Yes", LEVELS[0]))
    )
    case_id = connection.execute("SELECT id FROM cases").fetchone()[0]

    with pytest.raises(ValueError):
        add_case_note(connection, case_id, "Ana", "   ")


def test_set_current_submission_resolves_duplicates(tmp_path) -> None:
    config = alert_config()
    connection = import_with_alerts(tmp_path, config)
    questionnaire, second = synthetic_mapped_preview(response_id="response-002")
    import_preview(
        connection, second, questionnaire, synthetic_import_scoring_config()
    )
    first_id, second_id = (
        row[0] for row in connection.execute("SELECT id FROM submissions ORDER BY id")
    )

    set_current_submission(connection, second_id)

    assert connection.execute(
        "SELECT id, is_current FROM submissions ORDER BY id"
    ).fetchall() == [(first_id, 0), (second_id, 1)]
