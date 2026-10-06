import csv
import io
import sqlite3
import unicodedata
from decimal import Decimal

import pytest

from tamizaje.database import (
    DuplicateImportError,
    InvalidPreviewError,
    connect_database,
    import_preview,
    initialize_database,
    is_imported,
)
from tamizaje.importers import detect_delimiter, preview_csv, sha256_bytes
from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import QuestionDefinition
from tamizaje.scoring_config import (
    AreaDefinition,
    AreaItem,
    ScoringConfig,
    ScoringOption,
)
from tamizaje.validation import validate_table


def synthetic_questionnaire() -> tuple[QuestionDefinition, ...]:
    definitions = (
        ("ADM_RESPONSE_ID", "Response ID", "administrative", True),
        ("ADM_STARTED_AT", "Start time", "administrative", True),
        ("ADM_COMPLETED_AT", "Completion time", "administrative", True),
        ("ADM_EMAIL", "Email", "administrative", True),
        ("ADM_NAME", "Name", "administrative", True),
        ("DG02", "Career", "single_choice", False),
        ("DG03", "Group", "single_choice", False),
        ("Q01", "Answer one", "single_choice", False),
        ("Q02", "Answer two", "single_choice", True),
    )
    return tuple(
        QuestionDefinition(
            question_code=code,
            forms_number=None if question_type == "administrative" else index,
            question_text=text,
            question_type=question_type,
            required=True,
            is_sensitive=is_sensitive,
            questionnaire_version="1.2",
            mapping_status="approved",
        )
        for index, (code, text, question_type, is_sensitive) in enumerate(
            definitions, start=1
        )
    )


def synthetic_mapped_preview(
    *,
    response_id: str = "response-001",
    email: str = "student@example.edu",
    name: str = "Synthetic Student",
    career: str = "Synthetic Career",
    group: str = "S-01",
    max_rows: int | None = None,
):
    questionnaire = synthetic_questionnaire()
    headers = ",".join(question.question_text for question in questionnaire)
    values = ",".join(
        (
            response_id,
            "2026-01-01 09:00",
            "2026-01-01 09:10",
            email,
            name,
            career,
            group,
            "Yes",
            "No",
        )
    )
    preview = preview_csv(
        "synthetic.csv",
        f"{headers}\n{values}\n".encode(),
        max_rows=max_rows,
        questionnaire=questionnaire,
    )
    return questionnaire, preview


def synthetic_import_scoring_config() -> ScoringConfig:
    return ScoringConfig(
        version="test",
        scale_min=Decimal("1"),
        scale_max=Decimal("5"),
        incomplete_area_policy="no_score",
        areas=(
            AreaDefinition(
                "A01", "Synthetic", 2, 2, Decimal("70"), Decimal("40")
            ),
        ),
        items=(
            AreaItem("A01", "Q01", Decimal("1")),
            AreaItem("A01", "Q02", Decimal("1")),
        ),
        options=(
            ScoringOption("Q01", "Yes", None, Decimal("5"), True),
            ScoringOption("Q02", "No", None, Decimal("1"), True),
        ),
    )


def test_normalize_text_uses_nfc_and_normalizes_line_endings() -> None:
    decomposed = unicodedata.normalize("NFD", "  Sí\r\nacepto  ")

    assert normalize_text(decomposed) == "Sí\nacepto"


def test_validate_table_accepts_consistent_rows() -> None:
    result = validate_table(["ID", "Respuesta"], [["1", "Sí"], ["2", "No"]])

    assert result.is_valid
    assert result.errors == ()


def test_validate_table_rejects_empty_file() -> None:
    result = validate_table([], [])

    assert [issue.code for issue in result.errors] == ["empty_file"]


def test_validate_table_rejects_empty_and_normalized_duplicate_headers() -> None:
    result = validate_table(["Correo", " Correo ", ""], [])

    assert {issue.code for issue in result.errors} == {
        "duplicate_header",
        "empty_header",
    }


def test_validate_table_reports_row_number_without_cell_values() -> None:
    secret = "RESPUESTA_SECRETA"
    result = validate_table(["A", "B"], [[secret]])

    assert result.errors[0].code == "irregular_row"
    assert result.errors[0].row_number == 2
    assert secret not in repr(result)
    assert secret not in result.errors[0].message


def test_sha256_bytes_is_deterministic() -> None:
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_preview_csv_detects_utf8_bom_and_delimiter() -> None:
    content = "ID;Respuesta\n1;Sí\n".encode("utf-8-sig")

    preview = preview_csv("respuestas.csv", content)

    assert preview.encoding == "utf-8-sig"
    assert preview.delimiter == ";"
    assert preview.row_count == 1
    assert preview.column_count == 2
    assert preview.validation.is_valid


def test_detect_delimiter_handles_wide_headers_with_commas() -> None:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([f"Pregunta {index}, detalle " + "x" * 80 for index in range(105)])
    writer.writerow(["respuesta"] * 105)

    assert detect_delimiter(output.getvalue()) == ";"


def test_preview_csv_falls_back_to_cp1252() -> None:
    content = "ID;Nombre\n1;José\n".encode("cp1252")

    preview = preview_csv("respuestas.csv", content)

    assert preview.encoding == "cp1252"
    assert preview.row_count == 1


def test_preview_csv_limits_data_rows() -> None:
    content = b"ID,Respuesta\n1,Uno\n2,Dos\n3,Tres\n"

    preview = preview_csv("respuestas.csv", content, max_rows=2)

    assert preview.row_count == 2
    assert preview.total_row_count is None
    assert preview.is_limited


def test_preview_skips_test_rows_and_preserves_source_lines() -> None:
    rows = "".join(f"{index},Value {index}\n" for index in range(1, 17))
    content = f"ID,Answer\n{rows}".encode()

    preview = preview_csv("synthetic.csv", content, skip_rows=14)

    assert preview.row_count == 2
    assert preview.source_row_numbers == (16, 17)
    assert not preview.is_limited


def test_preview_safe_mode_preserves_test_source_lines() -> None:
    rows = "".join(f"{index},Value {index}\n" for index in range(1, 17))
    content = f"ID,Answer\n{rows}".encode()

    preview = preview_csv("synthetic.csv", content, max_rows=14)

    assert preview.source_row_numbers == tuple(range(2, 16))
    assert preview.is_limited


def test_preview_does_not_expose_responses() -> None:
    secret = "RESPUESTA_SECRETA"
    preview = preview_csv("respuestas.csv", f"ID,Texto\n1,{secret}\n".encode())

    assert secret not in repr(preview)
    assert secret not in str(preview.summary())
    assert set(preview.summary()) == {
        "filename",
        "sha256_short",
        "encoding",
        "delimiter",
        "row_count",
        "total_row_count",
        "column_count",
        "is_limited",
        "error_count",
        "warning_count",
    }


def test_preview_integrates_questionnaire_mapping() -> None:
    questionnaire = (
        QuestionDefinition(
            question_code="Q01",
            forms_number=1,
            question_text="ID",
            question_type="administrative",
            required=True,
            is_sensitive=True,
            questionnaire_version="0.1",
            mapping_status="approved",
        ),
        QuestionDefinition(
            question_code="Q02",
            forms_number=2,
            question_text="Answer",
            question_type="single_choice",
            required=False,
            is_sensitive=False,
            questionnaire_version="0.1",
            mapping_status="approved",
        ),
    )

    preview = preview_csv(
        "synthetic.csv", b"ID,Answer\n1,Yes\n", questionnaire=questionnaire
    )

    assert preview.mapping is not None
    assert preview.mapping.is_valid


def test_database_rejects_preview_with_incomplete_mapping(tmp_path) -> None:
    preview = preview_csv("synthetic.csv", b"Unknown,Other\n1,2\n", questionnaire=())
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    with pytest.raises(InvalidPreviewError):
        import_preview(connection, preview, ())


def test_database_initializes_normalized_schema(tmp_path) -> None:
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    student_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(students)")
    }
    submission_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(submissions)")
    }
    response_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(responses)")
    }

    assert {
        "student_upn",
        "student_upn_normalized",
        "student_name",
        "career",
        "group_name",
    } <= student_columns
    assert {
        "external_response_id",
        "student_id",
        "source_row_number",
        "started_at",
        "submitted_at",
        "is_current",
        "duplicate_student_submission",
    } <= submission_columns
    assert {
        "question_code",
        "response_raw",
        "response_normalized",
        "is_sensitive",
    } <= response_columns


def test_database_separates_student_submission_and_responses(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    import_preview(connection, preview, questionnaire)

    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 2
    assert connection.execute(
        "SELECT student_upn, student_name, career, group_name FROM students"
    ).fetchone() == (
        "student@example.edu",
        "Synthetic Student",
        "Synthetic Career",
        "S-01",
    )
    assert connection.execute(
        "SELECT external_response_id, started_at, submitted_at, source_row_number "
        "FROM submissions"
    ).fetchone() == (
        "response-001",
        "2026-01-01 09:00",
        "2026-01-01 09:10",
        2,
    )
    assert connection.execute(
        "SELECT question_code, is_sensitive FROM responses ORDER BY question_code"
    ).fetchall() == [("Q01", 0), ("Q02", 1)]


def test_import_persists_scoring_in_same_transaction(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    import_preview(
        connection,
        preview,
        questionnaire,
        synthetic_import_scoring_config(),
    )

    assert connection.execute(
        "SELECT area_code, normalized_score, traffic_light, scoring_version "
        "FROM area_results"
    ).fetchall() == [("A01", "50.0", "Amarillo", "test")]


def test_scoring_failure_rolls_back_complete_import(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    connection.execute(
        """
        CREATE TRIGGER force_area_result_failure
        BEFORE INSERT ON area_results
        BEGIN
            SELECT RAISE(ABORT, 'forced failure');
        END
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        import_preview(
            connection,
            preview,
            questionnaire,
            synthetic_import_scoring_config(),
        )

    for table in (
        "imports",
        "students",
        "submissions",
        "responses",
        "area_results",
    ):
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_database_rejects_empty_specialized_value_atomically(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview(email="")
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    with pytest.raises(InvalidPreviewError):
        import_preview(connection, preview, questionnaire)

    for table in ("imports", "students", "submissions", "responses"):
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_second_submission_reuses_student_and_requires_review(tmp_path) -> None:
    questionnaire, first = synthetic_mapped_preview()
    _, second = synthetic_mapped_preview(
        response_id="response-002",
        email="STUDENT@example.edu",
        name="Changed Name",
        career="Changed Career",
        group="S-99",
    )
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    import_preview(connection, first, questionnaire)
    import_preview(connection, second, questionnaire)

    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
    assert connection.execute(
        "SELECT is_current, duplicate_student_submission "
        "FROM submissions ORDER BY id"
    ).fetchall() == [(1, 0), (0, 1)]
    assert connection.execute(
        "SELECT student_name, career, group_name FROM students"
    ).fetchone() == ("Synthetic Student", "Synthetic Career", "S-01")


def test_database_rejects_duplicate_external_response_id_atomically(
    tmp_path,
) -> None:
    questionnaire, first = synthetic_mapped_preview()
    _, duplicate = synthetic_mapped_preview(
        response_id="response-001",
        email="other@example.edu",
    )
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    import_preview(connection, first, questionnaire)

    with pytest.raises(DuplicateImportError):
        import_preview(connection, duplicate, questionnaire)

    assert connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 2


def test_database_rejects_incomplete_specialized_mapping(
    tmp_path,
) -> None:
    questionnaire = (
        QuestionDefinition(
            question_code="ADM_EMAIL",
            question_text="Email",
            question_type="administrative",
            required=True,
            is_sensitive=True,
            questionnaire_version="1.2",
            mapping_status="approved",
        ),
        QuestionDefinition(
            question_code="Q01",
            forms_number=1,
            question_text="Answer",
            question_type="single_choice",
            required=True,
            is_sensitive=False,
            questionnaire_version="1.2",
            mapping_status="approved",
        ),
    )
    preview = preview_csv(
        "synthetic.csv",
        b"Email,Answer\nstudent@example.edu,Yes\n",
        questionnaire=questionnaire,
    )
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    with pytest.raises(InvalidPreviewError):
        import_preview(connection, preview, questionnaire)


def test_database_persists_import_submissions_and_responses(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    import_id = import_preview(connection, preview, questionnaire)

    assert import_id > 0
    assert is_imported(connection, preview.sha256)
    assert connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 2


def test_database_rejects_duplicate_hash(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    import_preview(connection, preview, questionnaire)

    with pytest.raises(DuplicateImportError):
        import_preview(connection, preview, questionnaire)

    assert connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1


def test_database_rejects_limited_preview(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview(max_rows=1)
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)

    with pytest.raises(InvalidPreviewError):
        import_preview(connection, preview, questionnaire)


def test_database_rolls_back_complete_import_on_failure(tmp_path) -> None:
    questionnaire, preview = synthetic_mapped_preview()
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    connection.execute(
        """
        CREATE TRIGGER force_response_failure
        BEFORE INSERT ON responses
        BEGIN
            SELECT RAISE(ABORT, 'forced failure');
        END
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        import_preview(connection, preview, questionnaire)

    assert connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0
