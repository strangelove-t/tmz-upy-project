"""Reportes PDF por lista blanca y manifiesto de entrega."""

import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from tamizaje.database import record_export
from tamizaje.models import EngineConfig
from tamizaje.questionnaire import load_questionnaire
from tamizaje.report_edits import apply_edits, load_edits
from tamizaje.sensitive_summary import (
    build_sensitive_summary,
    load_sensitive_config,
)
from tamizaje.student_report import render_student_pdf
from tamizaje.tutor_report import render_tutor_pdf

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"
CONFIG_DIR = Path(__file__).parents[2] / "config"


class ReportError(ValueError):
    """El reporte no puede generarse con los campos autorizados."""


@dataclass(frozen=True)
class ReportTemplate:
    template_version: str
    report_type: str
    title: str
    fields: tuple[str, ...]
    areas: tuple[str, ...] | None
    resources: tuple[str, ...]
    disclaimer: str
    contact: str = ""


@dataclass(frozen=True)
class AreaLine:
    area_code: str
    area_name: str
    score: Decimal | None
    traffic_light: str | None
    recommendation: str | None
    description: str
    interpretation: str


@dataclass(frozen=True)
class ReportContent:
    introduction: str
    traffic_light_legend: dict[str, str]
    group_level_explanations: dict[str, str]
    interpretations: dict[str, str]
    areas: dict[str, str]
    student_introduction: str
    student_labels: dict[str, str]


def load_report_content(
    engine: EngineConfig, config_dir: Path = CONFIG_DIR
) -> ReportContent:
    try:
        raw = yaml.safe_load(
            (config_dir / "report_content.yaml").read_text(encoding="utf-8")
        )
        content = ReportContent(
            introduction=str(raw["introduction"]),
            traffic_light_legend={
                str(key): str(value)
                for key, value in raw["traffic_light_legend"].items()
            },
            group_level_explanations={
                str(key): str(value)
                for key, value in raw["group_level_explanations"].items()
            },
            interpretations={
                str(key): str(value) for key, value in raw["interpretations"].items()
            },
            areas={str(key): str(value) for key, value in raw["areas"].items()},
            student_introduction=str(raw["student_introduction"]).strip(),
            student_labels={
                str(key): str(value).strip()
                for key, value in raw["student_labels"].items()
            },
        )
    except (OSError, KeyError, TypeError, yaml.YAMLError, AttributeError) as error:
        raise ReportError(
            "El contenido explicativo del reporte es inválido."
        ) from error
    area_codes = {area.area_code for area in engine.scoring.areas}
    if set(content.areas) != area_codes:
        raise ReportError("Las descripciones no cubren exactamente las áreas activas.")
    expected = {"Verde", "Amarillo", "Rojo", "Pendiente de revisión"}
    if (
        set(content.traffic_light_legend) != expected
        or set(content.interpretations) != expected
    ):
        raise ReportError("La explicación del semáforo está incompleta.")
    if set(content.group_level_explanations) != set(engine.alerts.levels) or not all(
        content.group_level_explanations.values()
    ):
        raise ReportError("La explicación de niveles grupales está incompleta.")
    if (
        set(content.student_labels) != expected
        or not all(content.student_labels.values())
        or not content.student_introduction
    ):
        raise ReportError("El texto del reporte del alumno está incompleto.")
    return content


def load_template(report_type: str, templates_dir: Path = TEMPLATES_DIR):
    try:
        raw = json.loads(
            (templates_dir / f"{report_type}_report.json").read_text(encoding="utf-8")
        )
        template = ReportTemplate(
            template_version=str(raw["template_version"]),
            report_type=str(raw["report_type"]),
            title=str(raw["title"]),
            fields=tuple(raw["fields"]),
            areas=tuple(raw["areas"]) if "areas" in raw else None,
            resources=tuple(raw.get("resources", ())),
            disclaimer=str(raw["disclaimer"]),
            contact=str(raw.get("contact", "")).strip(),
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ReportError(f"Plantilla {report_type} inválida.") from error
    if template.report_type != report_type:
        raise ReportError(f"Plantilla {report_type} inválida.")
    return template


def safe_filename_fragment(value: str, max_length: int = 160) -> str:
    """Fragmento legible sin separadores ni caracteres peligrosos para Windows."""
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", plain)
    return safe[:max_length].strip("._-") or "sin_nombre"


def report_filename(
    report_type: str, external_response_id: str, student_name: str
) -> str:
    """Nombre legible y determinista, con sufijo para evitar colisiones."""
    digest = hashlib.sha256(external_response_id.encode("utf-8")).hexdigest()[:16]
    return f"{report_type}_{safe_filename_fragment(student_name)}_{digest}.pdf"


def _score_scale(engine: EngineConfig) -> dict[str, int] | None:
    """Umbrales comunes en enteros; None si las áreas no comparten la escala."""
    thresholds = {(area.green_min, area.yellow_min) for area in engine.scoring.areas}
    if len(thresholds) != 1:
        return None
    green, yellow = thresholds.pop()
    if green != int(green) or yellow != int(yellow):
        return None
    return {"green_min": int(green), "yellow_min": int(yellow)}


def _spreadsheet_safe(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _area_lines(
    connection: sqlite3.Connection,
    submission_id: int,
    engine: EngineConfig,
    area_codes: tuple[str, ...] | None,
    audience: str,
) -> list[AreaLine]:
    content = load_report_content(engine)
    recommendation_text = {
        recommendation.recommendation_code: (
            recommendation.student_recommendation
            if audience == "student"
            else recommendation.staff_recommendation
        )
        for recommendation in engine.recommendations
    }
    stored = {
        row[0]: row[1:]
        for row in connection.execute(
            "SELECT area_code, normalized_score, traffic_light, is_complete, "
            "recommendation_code FROM area_results "
            "WHERE submission_id = ? AND scoring_version = ?",
            (submission_id, engine.scoring.version),
        )
    }
    lines = []
    for area in engine.scoring.areas:
        if area_codes is not None and area.area_code not in area_codes:
            continue
        score, light, complete, recommendation_code = stored.get(
            area.area_code, (None, None, 0, None)
        )
        lines.append(
            AreaLine(
                area_code=area.area_code,
                area_name=area.area_name,
                score=Decimal(score) if complete and score is not None else None,
                traffic_light=light if complete else None,
                recommendation=recommendation_text.get(recommendation_code),
                description=content.areas[area.area_code],
                interpretation=content.interpretations[
                    light if complete and light is not None else "Pendiente de revisión"
                ],
            )
        )
    return lines


def build_report_data(
    connection: sqlite3.Connection,
    submission_id: int,
    engine: EngineConfig,
    template: ReportTemplate,
    *,
    include_sensitive: bool = False,
) -> dict:
    """Construye sólo los campos de la lista blanca de la plantilla.

    Nunca consulta respuestas, alertas, casos ni notas: esa información no
    puede filtrarse a un reporte aunque una plantilla la solicite.
    """
    row = connection.execute(
        "SELECT st.student_name, st.career, st.group_name "
        "FROM submissions su JOIN students st ON st.id = su.student_id "
        "WHERE su.id = ?",
        (submission_id,),
    ).fetchone()
    if row is None:
        raise ReportError("El envío no existe.")
    lines = _area_lines(
        connection, submission_id, engine, template.areas, template.report_type
    )
    content = load_report_content(engine)
    available = {
        "student_name": row[0],
        "career": row[1],
        "group_name": row[2],
        "generated_at": datetime.now(engine.report_timezone).strftime("%Y-%m-%d"),
        "scoring_version": engine.scoring.version,
        "introduction": content.introduction,
        "traffic_light_legend": content.traffic_light_legend,
        "areas": lines,
        "strengths": [
            line.area_name for line in lines if line.traffic_light == "Verde"
        ],
        "opportunities": [
            line.area_name
            for line in lines
            if line.traffic_light in ("Amarillo", "Rojo")
        ],
        "recommendations": [
            (line.area_name, line.recommendation)
            for line in lines
            if line.recommendation
        ],
        "resources": list(template.resources),
        "disclaimer": template.disclaimer,
        "student_introduction": content.student_introduction,
        "student_labels": content.student_labels,
        "score_scale": _score_scale(engine),
        "contact": template.contact,
    }
    unknown = set(template.fields) - available.keys()
    if unknown:
        raise ReportError(f"Campos no autorizados en la plantilla: {sorted(unknown)}")
    data = {field: available[field] for field in template.fields}
    if include_sensitive:
        if template.report_type != "tutor":
            raise ReportError("El reporte del alumno no admite información sensible.")
        questionnaire = load_questionnaire(CONFIG_DIR / "questionnaire.csv")
        config = load_sensitive_config(CONFIG_DIR, questionnaire)
        data["sensitive_summary"] = build_sensitive_summary(
            connection, submission_id, config
        )
    return data


def render_pdf(data: dict, template: ReportTemplate) -> bytes:
    if template.report_type == "student":
        return render_student_pdf(data, template.title)
    return render_tutor_pdf(data, template.title)


def prepare_report(
    connection: sqlite3.Connection,
    submission_id: int,
    engine: EngineConfig,
    report_type: str,
    *,
    include_sensitive: bool = False,
) -> tuple[ReportTemplate, dict]:
    """Datos de la lista blanca con los textos editados y notas guardados."""
    template = load_template(report_type)
    data = build_report_data(
        connection,
        submission_id,
        engine,
        template,
        include_sensitive=include_sensitive,
    )
    edits = load_edits(connection, report_type, str(submission_id))
    return template, apply_edits(data, report_type, edits)


def generate_report(
    connection: sqlite3.Connection,
    submission_id: int,
    engine: EngineConfig,
    report_type: str,
    *,
    include_sensitive: bool = False,
) -> tuple[str, bytes]:
    external_id = connection.execute(
        "SELECT external_response_id FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if external_id is None:
        raise ReportError("El envío no existe.")
    template, data = prepare_report(
        connection,
        submission_id,
        engine,
        report_type,
        include_sensitive=include_sensitive,
    )
    return (
        report_filename(report_type, external_id[0], data["student_name"]),
        render_pdf(data, template),
    )


def export_batch(
    connection: sqlite3.Connection,
    engine: EngineConfig,
    output_dir: Path,
    *,
    include_sensitive_tutor: bool = False,
) -> Path:
    """Genera ambos PDFs de cada envío vigente y un manifiesto correo → archivo."""
    output_dir.mkdir(parents=True, exist_ok=True)
    submissions = connection.execute(
        "SELECT su.id, st.student_upn, st.student_name FROM submissions su "
        "JOIN students st ON st.id = su.student_id WHERE su.is_current = 1 "
        "ORDER BY su.id"
    ).fetchall()
    manifest_path = output_dir / "manifiesto.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["correo", "nombre", "reporte_estudiante", "expediente_tutor"])
        for submission_id, email, name in submissions:
            files = []
            for report_type in ("student", "tutor"):
                includes_sensitive = report_type == "tutor" and include_sensitive_tutor
                filename, content = generate_report(
                    connection,
                    submission_id,
                    engine,
                    report_type,
                    include_sensitive=includes_sensitive,
                )
                (output_dir / filename).write_bytes(content)
                record_export(
                    connection,
                    submission_id,
                    report_type,
                    str(output_dir / filename),
                    load_template(report_type).template_version,
                    includes_sensitive_summary=includes_sensitive,
                )
                files.append(filename)
            writer.writerow([_spreadsheet_safe(email), _spreadsheet_safe(name), *files])
    return manifest_path
