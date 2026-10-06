import csv
import io

import pytest
from pydantic import ValidationError

from tamizaje.questionnaire import (
    QuestionAlias,
    QuestionDefinition,
    QuestionnaireCatalogError,
    compare_headers,
    load_questionnaire,
    load_questionnaire_aliases,
)
from tamizaje.questionnaire_draft import (
    build_questionnaire_draft,
    read_pending_headers,
    write_questionnaire_draft,
)


def approved_question(**overrides: object) -> QuestionDefinition:
    values: dict[str, object] = {
        "question_code": "MO09",
        "forms_number": 36,
        "question_text": "He pensado en abandonar la universidad.",
        "question_type": "likert_frequency",
        "required": True,
        "is_sensitive": False,
        "questionnaire_version": "0.1",
        "mapping_status": "approved",
    }
    values.update(overrides)
    return QuestionDefinition(**values)


def test_question_definition_accepts_approved_question() -> None:
    question = approved_question()

    assert question.question_code == "MO09"
    assert question.forms_number == 36


def test_question_definition_accepts_integer_type() -> None:
    question = approved_question(
        question_code="DG01",
        forms_number=2,
        question_type="integer",
    )

    assert question.question_type == "integer"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question_code", ""),
        ("forms_number", 0),
        ("mapping_status", "guessed"),
    ],
)
def test_question_definition_rejects_invalid_approved_fields(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        approved_question(**{field: value})


def test_question_definition_allows_pending_row_without_mapping() -> None:
    question = QuestionDefinition(
        question_text="Pregunta pendiente",
        questionnaire_version="0.1",
        mapping_status="pending_review",
    )

    assert question.question_code is None
    assert question.forms_number is None


def test_approved_administrative_field_does_not_require_forms_number() -> None:
    question = QuestionDefinition(
        question_code="ADM_EMAIL",
        question_text="Email",
        question_type="administrative",
        required=True,
        is_sensitive=True,
        questionnaire_version="1.2",
        mapping_status="approved",
    )

    assert question.forms_number is None


def test_question_definition_accepts_verified_text_without_classification() -> None:
    question = QuestionDefinition(
        question_code="PA01",
        forms_number=8,
        question_text="Pregunta verificada",
        questionnaire_version="1.2",
        mapping_status="verified_text",
    )

    assert question.question_type is None


def test_verified_text_requires_code_and_forms_number() -> None:
    with pytest.raises(ValidationError):
        QuestionDefinition(
            question_text="Pregunta incompleta",
            questionnaire_version="1.2",
            mapping_status="verified_text",
        )


def test_load_questionnaire_rejects_duplicate_codes_without_exposing_values(
    tmp_path,
) -> None:
    path = tmp_path / "questionnaire.csv"
    fieldnames = [
        "QuestionCode",
        "FormsNumber",
        "QuestionText",
        "QuestionType",
        "Required",
        "IsSensitive",
        "QuestionnaireVersion",
        "MappingStatus",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "QuestionCode": "SECRET_CODE",
                "FormsNumber": "1",
                "QuestionText": "Primera pregunta",
                "QuestionType": "single_choice",
                "Required": "true",
                "IsSensitive": "false",
                "QuestionnaireVersion": "0.1",
                "MappingStatus": "approved",
            }
        )
        writer.writerow(
            {
                "QuestionCode": "SECRET_CODE",
                "FormsNumber": "2",
                "QuestionText": "Segunda pregunta",
                "QuestionType": "single_choice",
                "Required": "true",
                "IsSensitive": "false",
                "QuestionnaireVersion": "0.1",
                "MappingStatus": "approved",
            }
        )

    with pytest.raises(QuestionnaireCatalogError) as error:
        load_questionnaire(path)

    assert "fila 3" in str(error.value).lower()
    assert "SECRET_CODE" not in str(error.value)


def test_build_questionnaire_draft_uses_only_headers() -> None:
    secret = "RESPUESTA_SECRETA"
    content = f"ID;Pregunta\n1;{secret}\n".encode()

    draft = build_questionnaire_draft("respuestas.csv", content)

    assert len(draft.rows) == 2
    assert [row.source_column_index for row in draft.rows] == [1, 2]
    assert all(row.mapping_status == "pending_review" for row in draft.rows)
    assert all(row.question_code == "" for row in draft.rows)
    assert secret not in repr(draft)


def test_write_questionnaire_draft_contains_no_responses(tmp_path) -> None:
    secret = "RESPUESTA_SECRETA"
    draft = build_questionnaire_draft(
        "respuestas.csv", f"ID;Pregunta\n1;{secret}\n".encode()
    )
    path = tmp_path / "questionnaire_draft.csv"

    write_questionnaire_draft(draft, path)

    output = path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(output)))
    assert len(rows) == 2
    assert secret not in output
    assert rows[0]["SourceColumnIndex"] == "1"
    assert rows[0]["MappingStatus"] == "pending_review"


def test_read_pending_headers_reads_only_pending_normalized_headers(tmp_path) -> None:
    draft = build_questionnaire_draft("respuestas.csv", b"ID;Pregunta\n1;Valor\n")
    path = tmp_path / "questionnaire_draft.csv"
    write_questionnaire_draft(draft, path)

    assert read_pending_headers(path) == ("ID", "Pregunta")


def test_compare_headers_maps_exact_normalized_text() -> None:
    questionnaire = (approved_question(question_text="  Pregunta uno  "),)

    result = compare_headers(("Pregunta uno",), questionnaire)

    assert result.is_valid
    assert result.approved_count == 1
    assert result.assignments[0].question_code == "MO09"


def test_compare_headers_reports_pending_and_unknown_indices() -> None:
    questionnaire = (
        QuestionDefinition(
            question_text="Pregunta pendiente",
            questionnaire_version="0.1",
            mapping_status="pending_review",
        ),
    )

    result = compare_headers(
        ("Pregunta pendiente", "Columna desconocida"), questionnaire
    )

    assert result.pending_indices == (1,)
    assert result.unknown_indices == (2,)
    assert not result.is_valid


def test_compare_headers_reports_verified_text_separately() -> None:
    questionnaire = (
        QuestionDefinition(
            question_code="PA01",
            forms_number=8,
            question_text="Pregunta verificada",
            questionnaire_version="1.2",
            mapping_status="verified_text",
        ),
    )

    result = compare_headers(("Pregunta verificada",), questionnaire)

    assert result.verified_indices == (1,)
    assert result.verified_count == 1
    assert not result.is_valid


def test_compare_headers_reports_missing_required_code() -> None:
    questionnaire = (approved_question(required=True),)

    result = compare_headers(("Otra columna",), questionnaire)

    assert result.missing_required_codes == ("MO09",)
    assert not result.is_valid


def test_compare_headers_reports_ambiguous_index() -> None:
    questionnaire = (
        approved_question(question_code="Q01", forms_number=1, question_text="Igual"),
        approved_question(question_code="Q02", forms_number=2, question_text="Igual"),
    )

    result = compare_headers(("Igual",), questionnaire)

    assert result.ambiguous_indices == (1,)
    assert not result.is_valid


def test_compare_headers_accepts_explicit_legacy_alias() -> None:
    questionnaire = (
        approved_question(
            question_code="PE02",
            forms_number=92,
            question_text=(
                "¿Qué tan probable consideras que continúes estudiando en esta "
                "universidad durante el próximo cuatrimestre?"
            ),
            question_type="ordinal_choice",
            questionnaire_version="1.2",
        ),
    )
    aliases = (
        QuestionAlias(
            alias_text=(
                "¿Qué tan probable consideras que continúes estudiando en esta "
                "universidad durante el próximo semestre?"
            ),
            question_code="PE02",
            source_questionnaire_version="pre-1.2",
            canonical_questionnaire_version="1.2",
            reason="Corrección de periodo académico",
        ),
    )

    result = compare_headers(
        (
            "¿Qué tan probable consideras que continúes estudiando en esta "
            "universidad durante el próximo semestre?",
        ),
        questionnaire,
        aliases=aliases,
    )

    assert result.is_valid
    assert result.assignments[0].question_code == "PE02"


def test_compare_headers_keeps_verified_alias_unapproved() -> None:
    questionnaire = (
        QuestionDefinition(
            question_code="CN01",
            forms_number=1,
            question_text="Texto canónico completo",
            questionnaire_version="1.2",
            mapping_status="verified_text",
        ),
    )
    aliases = (
        QuestionAlias(
            alias_text="Texto truncado",
            question_code="CN01",
            source_questionnaire_version="1.2-export",
            canonical_questionnaire_version="1.2",
            reason="Truncamiento técnico",
        ),
    )

    result = compare_headers(("Texto truncado",), questionnaire, aliases=aliases)

    assert result.verified_indices == (1,)
    assert result.assignments == ()


def test_load_questionnaire_aliases_rejects_unknown_code(tmp_path) -> None:
    path = tmp_path / "questionnaire_aliases.csv"
    path.write_text(
        "AliasText,QuestionCode,SourceQuestionnaireVersion,"
        "CanonicalQuestionnaireVersion,Reason\n"
        "Texto anterior,UNKNOWN,pre-1.2,1.2,Corrección\n",
        encoding="utf-8",
    )

    with pytest.raises(QuestionnaireCatalogError):
        load_questionnaire_aliases(path, (approved_question(),))
