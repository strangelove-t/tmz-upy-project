"""Piloto aislado con los 14 registros de prueba (líneas 2–15).

Reconstruye en memoria un CSV con el encabezado y sólo los primeros 14
registros, lo procesa en una base temporal y devuelve exclusivamente métricas
no sensibles. Nunca lee más allá del registro 14 ni escribe en
``data/tamizaje.db``.
"""

import csv
import io
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory

from tamizaje.database import (
    connect_database,
    import_preview,
    initialize_database,
    recalculate_all,
)
from tamizaje.importers import (
    CsvPreview,
    ImportErrorSafe,
    detect_delimiter,
    detect_encoding,
    preview_csv,
)
from tamizaje.models import load_engine_config
from tamizaje.questionnaire import (
    QuestionAlias,
    QuestionDefinition,
    load_questionnaire,
    load_questionnaire_aliases,
)
from tamizaje.reports import generate_report

TEST_ROWS = 14
PROJECT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class AcceptanceError(ValueError):
    """Fallo del piloto con un mensaje que no contiene valores del archivo."""


@dataclass(frozen=True)
class PilotResult:
    submissions: int
    source_lines: tuple[int, int]
    area_results: int
    complete_area_results: int
    alert_count: int
    case_count: int
    recalculated: int
    pdf_count: int
    questionnaire_version: str
    scoring_version: str
    rule_version: str
    temporary_files_removed: bool

    @property
    def passed(self) -> bool:
        return (
            self.submissions == TEST_ROWS
            and self.source_lines == (2, TEST_ROWS + 1)
            and self.recalculated == TEST_ROWS
            and self.pdf_count == TEST_ROWS * 2
            and self.temporary_files_removed
        )


def test_only_preview(
    filename: str,
    content: bytes,
    questionnaire: tuple[QuestionDefinition, ...],
    aliases: tuple[QuestionAlias, ...] = (),
) -> CsvPreview:
    """Encabezado + exactamente 14 registros; el resto del archivo no se lee."""
    try:
        encoding = detect_encoding(content)
        text = content.decode(encoding)
        delimiter = detect_delimiter(text)
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        records = list(islice(reader, TEST_ROWS + 1))
    except (UnicodeDecodeError, csv.Error, ImportErrorSafe) as error:
        raise AcceptanceError("No fue posible interpretar el CSV.") from error
    if len(records) < TEST_ROWS + 1:
        raise AcceptanceError(
            f"El archivo debe contener encabezado y {TEST_ROWS} registros de prueba."
        )

    stream = io.StringIO()
    csv.writer(stream, delimiter=delimiter, lineterminator="\n").writerows(records)
    return preview_csv(
        filename,
        stream.getvalue().encode("utf-8"),
        questionnaire=questionnaire,
        aliases=aliases,
    )


# El nombre empieza con "test_" por contrato del plan; no es una prueba.
test_only_preview.__test__ = False  # type: ignore[attr-defined]


def _valid_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF-") and content.rstrip().endswith(b"%%EOF")


def run_pilot(
    filename: str,
    content: bytes,
    workspace: Path,
    config_dir: Path = PROJECT_CONFIG_DIR,
) -> PilotResult:
    """Importa, recalcula y genera PDFs en un directorio temporal desechable."""
    questionnaire = load_questionnaire(config_dir / "questionnaire.csv")
    aliases = load_questionnaire_aliases(
        config_dir / "questionnaire_aliases.csv", questionnaire
    )
    engine = load_engine_config(config_dir)
    preview = test_only_preview(filename, content, questionnaire, aliases)
    if not preview.validation.is_valid:
        raise AcceptanceError(
            f"Validación estructural con {len(preview.validation.errors)} errores."
        )
    if preview.mapping is None or not preview.mapping.is_valid:
        raise AcceptanceError("El mapeo de encabezados no es válido.")

    workspace.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="piloto-", dir=workspace) as temporary:
        temporary_dir = Path(temporary)
        connection = connect_database(temporary_dir / "piloto.db")
        try:
            initialize_database(connection)
            import_preview(
                connection,
                preview,
                questionnaire,
                engine.scoring,
                alert_config=engine.alerts,
                recommendations=engine.recommendations,
            )
            recalculated = recalculate_all(
                connection, engine.scoring, engine.alerts, engine.recommendations
            )

            def count(sql: str, *params: str) -> int:
                return connection.execute(sql, params).fetchone()[0]

            lines = connection.execute(
                "SELECT MIN(source_row_number), MAX(source_row_number) "
                "FROM submissions"
            ).fetchone()
            submission_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM submissions WHERE is_current = 1 ORDER BY id"
                )
            ]
            pdf_dir = temporary_dir / "pdf"
            pdf_dir.mkdir()
            pdf_count = 0
            for submission_id in submission_ids:
                for report_type in ("student", "advisor"):
                    name, pdf = generate_report(
                        connection, submission_id, engine, report_type
                    )
                    (pdf_dir / name).write_bytes(pdf)
                    pdf_count += _valid_pdf((pdf_dir / name).read_bytes())

            result = dict(
                submissions=count("SELECT COUNT(*) FROM submissions"),
                source_lines=(int(lines[0]), int(lines[1])),
                area_results=count(
                    "SELECT COUNT(*) FROM area_results WHERE scoring_version = ?",
                    engine.scoring.version,
                ),
                complete_area_results=count(
                    "SELECT COUNT(*) FROM area_results "
                    "WHERE scoring_version = ? AND is_complete = 1",
                    engine.scoring.version,
                ),
                alert_count=count(
                    "SELECT COUNT(*) FROM alerts WHERE rule_version = ?",
                    engine.alerts.version,
                ),
                case_count=count("SELECT COUNT(*) FROM cases WHERE is_active = 1"),
                recalculated=recalculated,
                pdf_count=pdf_count,
                questionnaire_version=questionnaire[0].questionnaire_version,
                scoring_version=engine.scoring.version,
                rule_version=engine.alerts.version,
            )
        finally:
            connection.close()

    return PilotResult(**result, temporary_files_removed=not temporary_dir.exists())
