"""Reportes PDF por lista blanca y manifiesto de entrega."""

import csv
import hashlib
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path

import yaml
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tamizaje.database import record_export
from tamizaje.models import EngineConfig
from tamizaje.questionnaire import load_questionnaire
from tamizaje.sensitive_summary import (
    SensitiveSummary,
    build_sensitive_summary,
    load_sensitive_config,
)

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"
CONFIG_DIR = Path(__file__).parents[2] / "config"
LIGHT_COLORS = {
    "Verde": colors.HexColor("#2e7d32"),
    "Amarillo": colors.HexColor("#b28704"),
    "Rojo": colors.HexColor("#c62828"),
}


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
    interpretations: dict[str, str]
    areas: dict[str, str]


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
            interpretations={
                str(key): str(value)
                for key, value in raw["interpretations"].items()
            },
            areas={str(key): str(value) for key, value in raw["areas"].items()},
        )
    except (OSError, KeyError, TypeError, yaml.YAMLError, AttributeError) as error:
        raise ReportError(
            "El contenido explicativo del reporte es inválido."
        ) from error
    area_codes = {area.area_code for area in engine.scoring.areas}
    if set(content.areas) != area_codes:
        raise ReportError("Las descripciones no cubren exactamente las áreas activas.")
    expected = {"Verde", "Amarillo", "Rojo", "Pendiente de revisión"}
    if set(content.traffic_light_legend) != expected or set(
        content.interpretations
    ) != expected:
        raise ReportError("La explicación del semáforo está incompleta.")
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
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ReportError(f"Plantilla {report_type} inválida.") from error
    if template.report_type != report_type:
        raise ReportError(f"Plantilla {report_type} inválida.")
    return template


def report_filename(report_type: str, external_response_id: str) -> str:
    """Nombre determinista que no expone nombre ni correo."""
    digest = hashlib.sha256(external_response_id.encode("utf-8")).hexdigest()[:16]
    return f"{report_type}_{digest}.pdf"


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
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    story: list = [Paragraph(template.title, styles["Title"])]

    identity = [
        (label, data[field])
        for field, label in (
            ("student_name", "Nombre"),
            ("career", "Carrera"),
            ("group_name", "Grupo"),
            ("generated_at", "Fecha"),
            ("scoring_version", "Versión de scoring"),
        )
        if field in data
    ]
    if identity:
        table = Table(
            [
                [
                    Paragraph(f"<b>{label}</b>", body),
                    Paragraph(escape(str(value)), body),
                ]
                for label, value in identity
            ],
            colWidths=[4 * cm, 12 * cm],
        )
        story += [table, Spacer(1, 0.4 * cm)]

    if data.get("introduction"):
        story += [
            Paragraph(escape(data["introduction"]), body),
            Spacer(1, 0.3 * cm),
        ]

    if data.get("traffic_light_legend"):
        story.append(Paragraph("Cómo leer el semáforo", styles["Heading2"]))
        for label, explanation in data["traffic_light_legend"].items():
            story.append(
                Paragraph(f"<b>{escape(label)}:</b> {escape(explanation)}", body)
            )

    if "areas" in data:
        story.append(Paragraph("Resultados por área", styles["Heading2"]))
        rows = [["Área e interpretación", "Puntaje", "Semáforo"]]
        style = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ]
        for index, line in enumerate(data["areas"], start=1):
            rows.append(
                [
                    Paragraph(
                        f"<b>{escape(line.area_name)}</b><br/>"
                        f"{escape(line.description)}<br/>"
                        f"{escape(line.interpretation)}",
                        body,
                    ),
                    f"{line.score:.1f}" if line.score is not None else "—",
                    line.traffic_light or "Pendiente de revisión",
                ]
            )
            if line.traffic_light in LIGHT_COLORS:
                color = LIGHT_COLORS[line.traffic_light]
                style.append(("TEXTCOLOR", (2, index), (2, index), color))
        table = Table(rows, colWidths=[9 * cm, 3 * cm, 4 * cm])
        table.setStyle(TableStyle(style))
        story += [table, Spacer(1, 0.4 * cm)]

    for field, heading in (
        ("strengths", "Fortalezas"),
        ("opportunities", "Áreas de oportunidad"),
    ):
        if data.get(field):
            story.append(Paragraph(heading, styles["Heading2"]))
            story.append(Paragraph(escape(", ".join(data[field])), body))

    if data.get("recommendations"):
        heading = (
            "Recomendaciones para ti"
            if template.report_type == "student"
            else "Acciones sugeridas para la tutoría"
        )
        story.append(Paragraph(heading, styles["Heading2"]))
        for area_name, text in data["recommendations"]:
            story.append(
                Paragraph(f"<b>{escape(area_name)}:</b> {escape(text)}", body)
            )

    if data.get("resources"):
        story.append(Paragraph("Recursos institucionales", styles["Heading2"]))
        for resource in data["resources"]:
            story.append(Paragraph(f"• {escape(resource)}", body))

    sensitive: SensitiveSummary | None = data.get("sensitive_summary")
    if sensitive is not None and sensitive.has_sensitive_declaration:
        story.append(Paragraph("Condiciones y apoyos declarados", styles["Heading2"]))
        story.append(
            Paragraph(
                "<b>Confidencial — uso exclusivo de Orientación y Tutorías.</b>",
                body,
            )
        )
        for category in sensitive.categories:
            story.append(Paragraph(f"<b>{escape(category.label)}</b>", body))
            for label, value in category.fields:
                story.append(Paragraph(f"{escape(label)}: {escape(value)}", body))

    disclaimer = Paragraph(f"<i>{escape(template.disclaimer)}</i>", body)
    story += [Spacer(1, 0.6 * cm), disclaimer]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=template.title,
        invariant=1,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    document.build(story)
    return buffer.getvalue()


def generate_report(
    connection: sqlite3.Connection,
    submission_id: int,
    engine: EngineConfig,
    report_type: str,
    *,
    include_sensitive: bool = False,
) -> tuple[str, bytes]:
    template = load_template(report_type)
    external_id = connection.execute(
        "SELECT external_response_id FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if external_id is None:
        raise ReportError("El envío no existe.")
    data = build_report_data(
        connection,
        submission_id,
        engine,
        template,
        include_sensitive=include_sensitive,
    )
    return report_filename(report_type, external_id[0]), render_pdf(data, template)


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
