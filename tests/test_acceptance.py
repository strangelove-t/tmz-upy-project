import pytest
from synthetic_forms import project_config, synthetic_rows

from scripts import run_acceptance
from tamizaje.acceptance import AcceptanceError, run_pilot, test_only_preview

# Filas 16+ simulan datos reales: deben ignorarse por completo.
REAL_MARKER = "fila-real-confidencial"


def twenty_rows() -> bytes:
    questionnaire, engine = project_config()
    students = [{} for _ in range(14)] + [
        {"ADM_NAME": f"{REAL_MARKER}-{index}", "DC02": "Sí"} for index in range(6)
    ]
    return synthetic_rows(questionnaire, engine, students)


def test_test_only_preview_contains_header_and_first_14_rows() -> None:
    questionnaire, _ = project_config()

    preview = test_only_preview("local.csv", twenty_rows(), questionnaire)

    assert preview.row_count == 14
    assert preview.source_row_numbers == tuple(range(2, 16))
    assert not preview.is_limited
    assert preview.mapping.is_valid
    assert REAL_MARKER not in repr(preview.rows_raw)


def test_test_only_preview_rejects_files_with_fewer_rows() -> None:
    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [{} for _ in range(13)])

    with pytest.raises(AcceptanceError, match="14 registros"):
        test_only_preview("local.csv", content, questionnaire)


def test_run_pilot_imports_only_test_rows_into_temporary_database(tmp_path) -> None:
    result = run_pilot("local.csv", twenty_rows(), tmp_path)

    assert result.passed
    assert result.submissions == 14
    assert result.source_lines == (2, 15)
    assert result.area_results == 14 * 9
    assert result.complete_area_results == 14 * 9
    assert result.pdf_count == 14 * 2
    assert result.case_count == 0
    assert result.recalculated == 14
    assert result.scoring_version == "0.2"
    assert result.rule_version == "0.1"
    assert result.temporary_files_removed
    assert list(tmp_path.iterdir()) == []
    assert "synthetic" not in repr(result).lower()
    assert REAL_MARKER not in repr(result)


def run_script(tmp_path, monkeypatch, capsys, files: dict[str, bytes]) -> tuple:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name, content in files.items():
        (data_dir / name).write_bytes(content)
    monkeypatch.setattr(run_acceptance, "DATA_DIR", data_dir)
    code = run_acceptance.main()
    output = capsys.readouterr().out
    return code, output, data_dir


def test_script_reports_only_safe_metrics(tmp_path, monkeypatch, capsys) -> None:
    code, output, data_dir = run_script(
        tmp_path, monkeypatch, capsys, {"respuestas-nombre-secreto.csv": twenty_rows()}
    )

    assert code == 0
    assert "Envíos procesados: 14" in output
    assert "Líneas: 2–15" in output
    assert "PDF validados: 28" in output
    for forbidden in ("nombre-secreto", "synthetic", "Sintético", REAL_MARKER, "@"):
        assert forbidden not in output
    assert sorted(path.name for path in data_dir.iterdir()) == [
        "respuestas-nombre-secreto.csv"
    ]


@pytest.mark.parametrize("count", [0, 2])
def test_script_requires_exactly_one_csv_without_listing_names(
    tmp_path, monkeypatch, capsys, count
) -> None:
    files = {f"nombre-secreto-{index}.csv": b"a\n" for index in range(count)}

    code, output, _ = run_script(tmp_path, monkeypatch, capsys, files)

    assert code != 0
    assert "exactamente un archivo CSV" in output
    assert "nombre-secreto" not in output
