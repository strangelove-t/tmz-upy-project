from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tamizaje import SCORING_VERSION
from tamizaje.database import (
    connect_database,
    initialize_database,
    persist_area_results,
)
from tamizaje.scoring import score_responses
from tamizaje.scoring_config import (
    AreaDefinition,
    AreaItem,
    ScoringConfig,
    ScoringConfigError,
    ScoringOption,
    load_scoring_config,
)


def write_minimal_config(path: Path, *, expected_item_count: int = 1) -> None:
    path.mkdir()
    (path / "parameters.yaml").write_text(
        """active_scoring_version: "0.2"
scoring_versions:
  "0.2":
    scale_min: 1
    scale_max: 5
    incomplete_area_policy: no_score
""",
        encoding="utf-8",
    )
    (path / "areas.csv").write_text(
        "AreaCode,AreaName,ExpectedItemCount,MinimumValidItemCount,GreenMin,YellowMin,Version\n"
        f"A01,Synthetic area,{expected_item_count},1,70,40,0.2\n",
        encoding="utf-8",
    )
    (path / "area_items.csv").write_text(
        "AreaCode,QuestionCode,Weight,Version\nA01,Q01,1,0.2\n",
        encoding="utf-8",
    )
    (path / "scoring_options.csv").write_text(
        "QuestionCode,Response,ResponseAlias,CorrectedValue,IncludeInAverage,Version\n"
        "Q01,Yes,,5,true,0.2\n",
        encoding="utf-8",
    )
    (path / "questionnaire.csv").write_text(
        "QuestionCode,FormsNumber,QuestionText,QuestionType,Required,IsSensitive,QuestionnaireVersion,MappingStatus\n"
        "Q01,1,Synthetic question,single_choice,true,false,1.2,approved\n",
        encoding="utf-8",
    )


def test_scoring_version_matches_handoff() -> None:
    assert SCORING_VERSION == "0.2"


def test_load_scoring_config_selects_active_version(tmp_path) -> None:
    config_dir = tmp_path / "config"
    write_minimal_config(config_dir)

    config = load_scoring_config(config_dir)

    assert config.version == "0.2"
    assert config.scale_min == 1
    assert config.scale_max == 5
    assert [area.area_code for area in config.areas] == ["A01"]
    assert config.items[0].question_code == "Q01"
    assert config.options[0].corrected_value == 5


def test_load_scoring_config_rejects_inconsistent_item_count(tmp_path) -> None:
    config_dir = tmp_path / "config"
    write_minimal_config(config_dir, expected_item_count=2)

    with pytest.raises(ScoringConfigError, match="areas.csv"):
        load_scoring_config(config_dir)


@pytest.mark.parametrize(
    ("filename", "old", "new"),
    [
        (
            "parameters.yaml",
            'active_scoring_version: "0.2"',
            'active_scoring_version: "0.3"',
        ),
        ("areas.csv", ",70,40,0.2", ",30,40,0.2"),
        ("area_items.csv", "Q01,1,0.2", "Q01,0,0.2"),
        ("area_items.csv", "Q01,1,0.2", "Q99,1,0.2"),
        ("scoring_options.csv", ",5,true,0.2", ",6,true,0.2"),
    ],
)
def test_load_scoring_config_rejects_invalid_rules(
    tmp_path, filename, old, new
) -> None:
    config_dir = tmp_path / "config"
    write_minimal_config(config_dir)
    path = config_dir / filename
    path.write_text(
        path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )

    with pytest.raises(ScoringConfigError):
        load_scoring_config(config_dir)


def test_load_scoring_config_rejects_normalized_duplicate_option(tmp_path) -> None:
    config_dir = tmp_path / "config"
    write_minimal_config(config_dir)
    path = config_dir / "scoring_options.csv"
    path.write_text(
        path.read_text(encoding="utf-8") + "Q01,yes,,4,true,0.2\n",
        encoding="utf-8",
    )

    with pytest.raises(ScoringConfigError, match="scoring_options.csv"):
        load_scoring_config(config_dir)


def test_project_scoring_catalog_has_expected_v02_coverage() -> None:
    config = load_scoring_config(Path(__file__).parents[1] / "config")

    assert config.version == "0.2"
    assert len(config.areas) == 9
    assert len(config.items) == 64
    assert len(config.options) == 314
    assert {item.weight for item in config.items} == {1}

    values = {
        (option.question_code, option.response): option.corrected_value
        for option in config.options
    }
    assert values[("PA01", "Totalmente de acuerdo")] == 5
    assert values[("HO04", "Siempre")] == 1
    assert values[("PE02", "Probable")] == 4
    assert values[("CF05", "No aplica")] is None


def test_project_catalog_scores_all_nine_areas() -> None:
    config = load_scoring_config(Path(__file__).parents[1] / "config")
    first_included_option = {}
    for option in config.options:
        if option.include_in_average:
            first_included_option.setdefault(option.question_code, option.response)

    results = score_responses(first_included_option, config)

    assert len(results) == 9
    assert all(result.is_complete for result in results)


def synthetic_scoring_config(*, minimum_valid: int = 1) -> ScoringConfig:
    return ScoringConfig(
        version="test",
        scale_min=Decimal("1"),
        scale_max=Decimal("5"),
        incomplete_area_policy="no_score",
        areas=(
            AreaDefinition(
                area_code="A01",
                area_name="Synthetic",
                expected_item_count=2,
                minimum_valid_item_count=minimum_valid,
                green_min=Decimal("70"),
                yellow_min=Decimal("40"),
            ),
        ),
        items=(
            AreaItem("A01", "Q01", Decimal("1")),
            AreaItem("A01", "Q02", Decimal("3")),
        ),
        options=(
            ScoringOption("Q01", "Low", None, Decimal("1"), True),
            ScoringOption("Q01", "Boundary", None, Decimal("3.8"), True),
            ScoringOption("Q02", "High", None, Decimal("5"), True),
            ScoringOption("Q02", "No aplica", None, None, False),
        ),
    )


def test_score_responses_uses_configured_weights_and_thresholds() -> None:
    result = score_responses(
        {"Q01": "Low", "Q02": "High"}, synthetic_scoring_config()
    )[0]

    assert result.raw_average == Decimal("4")
    assert result.normalized_score == Decimal("75")
    assert result.traffic_light == "Verde"
    assert result.is_complete


def test_score_responses_excludes_not_applicable_option() -> None:
    result = score_responses(
        {"Q01": "Boundary", "Q02": "No aplica"},
        synthetic_scoring_config(minimum_valid=2),
    )[0]

    assert result.valid_item_count == 1
    assert result.applicable_item_count == 1
    assert result.is_complete
    assert result.normalized_score == Decimal("70.0")
    assert result.traffic_light == "Verde"


def test_score_responses_marks_unknown_answer_incomplete_without_value() -> None:
    result = score_responses(
        {"Q01": "Low", "Q02": "Unconfigured secret"},
        synthetic_scoring_config(minimum_valid=2),
    )[0]

    assert not result.is_complete
    assert result.raw_average is None
    assert result.normalized_score is None
    assert result.traffic_light is None
    assert result.issues == ("unknown_response:Q02",)
    assert "Unconfigured secret" not in repr(result)


def test_persist_area_results_keeps_versions_separate(tmp_path) -> None:
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    connection.execute(
        """
        INSERT INTO imports (
            filename, sha256, imported_at, questionnaire_version,
            scoring_version, row_count, column_count, status
        ) VALUES ('synthetic.csv', 'hash', 'now', '1.2', 'test', 1, 1, 'completed')
        """
    )
    connection.execute(
        """
        INSERT INTO students (
            student_upn, student_upn_normalized, student_name, career, group_name
        ) VALUES (
            'student@example.edu', 'student@example.edu',
            'Student', 'Career', 'G1'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO submissions (
            external_response_id, student_id, import_id, source_row_number,
            started_at, submitted_at, is_current, duplicate_student_submission
        ) VALUES ('response-1', 1, 1, 2, 'start', 'end', 1, 0)
        """
    )
    result = score_responses(
        {"Q01": "Low", "Q02": "High"}, synthetic_scoring_config()
    )

    persist_area_results(connection, 1, result)

    assert connection.execute(
        "SELECT raw_average, normalized_score, traffic_light, scoring_version "
        "FROM area_results"
    ).fetchone() == ("4", "75.00", "Verde", "test")

    persist_area_results(
        connection,
        1,
        tuple(replace(item, scoring_version="test-2") for item in result),
    )

    assert connection.execute(
        "SELECT scoring_version FROM area_results ORDER BY scoring_version"
    ).fetchall() == [("test",), ("test-2",)]
