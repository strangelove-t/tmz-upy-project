"""Resumen agregado para tutoría grupal, sin identificadores de estudiantes."""

import hashlib
import io
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tamizaje.cases import CASE_STATUSES
from tamizaje.models import EngineConfig

LIGHTS = ("Verde", "Amarillo", "Rojo", "Pendiente")


class GroupReportError(ValueError):
    """El grupo no cumple el umbral de confidencialidad."""


@dataclass(frozen=True)
class GroupAreaSummary:
    code: str
    name: str
    average: Decimal | None
    complete_count: int
    distribution: dict[str, int]

    @property
    def attention_count(self) -> int:
        return self.distribution["Amarillo"] + self.distribution["Rojo"]


@dataclass(frozen=True)
class GroupReport:
    career: str
    group_name: str
    generated_at: datetime
    student_count: int
    complete_results: int
    pending_results: int
    areas: tuple[GroupAreaSummary, ...]
    open_cases_by_level: dict[str, int]

    @property
    def focus_areas(self) -> tuple[GroupAreaSummary, ...]:
        ranked = sorted(self.areas, key=lambda area: (-area.attention_count, area.code))
        return tuple(area for area in ranked if area.attention_count > 0)[:3]


def build_group_report(
    connection: sqlite3.Connection,
    engine: EngineConfig,
    career: str,
    group_name: str,
) -> GroupReport:
    """Consulta sólo agregados de respuestas vigentes y reglas activas."""
    count = connection.execute(
        "SELECT COUNT(*) FROM submissions su "
        "JOIN students st ON st.id = su.student_id "
        "WHERE su.is_current = 1 AND st.career = ? AND st.group_name = ?",
        (career, group_name),
    ).fetchone()[0]
    if count == 0:
        raise GroupReportError("El grupo no existe o no tiene respuestas.")
    if count < engine.minimum_group_size:
        raise GroupReportError(
            f"Este grupo tiene menos de {engine.minimum_group_size} alumnos "
            "evaluados; no se puede mostrar ni descargar su resumen."
        )

    rows = connection.execute(
        """
        SELECT ar.area_code, ar.is_complete, ar.normalized_score, ar.traffic_light
        FROM area_results ar
        JOIN submissions su ON su.id = ar.submission_id
        JOIN students st ON st.id = su.student_id
        WHERE su.is_current = 1 AND st.career = ? AND st.group_name = ?
          AND ar.scoring_version = ?
        """,
        (career, group_name, engine.scoring.version),
    ).fetchall()
    by_area: dict[str, list[tuple]] = {
        area.area_code: [] for area in engine.scoring.areas
    }
    for code, complete, score, light in rows:
        if code in by_area:
            by_area[code].append((complete, score, light))

    summaries = []
    for definition in engine.scoring.areas:
        scores = []
        distribution = dict.fromkeys(LIGHTS, 0)
        for complete, score, light in by_area[definition.area_code]:
            if complete and score is not None and light in LIGHTS[:-1]:
                scores.append(Decimal(score))
                distribution[light] += 1
        distribution["Pendiente"] = count - len(scores)
        summaries.append(
            GroupAreaSummary(
                code=definition.area_code,
                name=definition.area_name,
                average=sum(scores) / len(scores) if scores else None,
                complete_count=len(scores),
                distribution=distribution,
            )
        )

    case_rows = connection.execute(
        """
        SELECT c.case_level, COUNT(*)
        FROM cases c
        JOIN submissions su ON su.id = c.submission_id
        JOIN students st ON st.id = su.student_id
        WHERE su.is_current = 1 AND c.is_active = 1 AND c.case_status != ?
          AND c.scoring_version = ? AND c.rule_version = ?
          AND st.career = ? AND st.group_name = ?
        GROUP BY c.case_level
        """,
        (
            CASE_STATUSES[-1],
            engine.scoring.version,
            engine.alerts.version,
            career,
            group_name,
        ),
    ).fetchall()
    counts = dict.fromkeys(engine.alerts.levels, 0)
    counts.update((level, number) for level, number in case_rows if level in counts)
    complete_results = sum(area.complete_count for area in summaries)
    return GroupReport(
        career=career,
        group_name=group_name,
        generated_at=datetime.now(engine.report_timezone),
        student_count=count,
        complete_results=complete_results,
        pending_results=count * len(summaries) - complete_results,
        areas=tuple(summaries),
        open_cases_by_level=counts,
    )


def group_report_filename(report: GroupReport) -> str:
    key = f"{report.career}\0{report.group_name}".encode()
    digest = hashlib.sha256(key).hexdigest()[:16]
    return f"grupo_{digest}_{report.generated_at:%Y%m%d}.pdf"


def render_group_pdf(report: GroupReport) -> bytes:
    output = io.BytesIO()
    total_results = report.complete_results + report.pending_results
    coverage = report.complete_results / total_results
    document = SimpleDocTemplate(
        output, pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm
    )
    styles = getSampleStyleSheet()
    normal = styles["BodyText"]
    small = ParagraphStyle("GroupSmall", parent=normal, fontSize=8, leading=10)
    story = [
        Paragraph("Resumen grupal para tutoría", styles["Title"]),
        Paragraph(
            f"Carrera: {escape(report.career)} · Grupo: {escape(report.group_name)}",
            normal,
        ),
        Paragraph(f"Generado: {report.generated_at:%d/%m/%Y %H:%M}", normal),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Alumnos evaluados: {report.student_count}", normal),
        Paragraph(
            "Resultados completos: "
            f"{report.complete_results}/{total_results} ({coverage:.0%})",
            normal,
        ),
        Spacer(1, 0.4 * cm),
        Paragraph("Resultados por área", styles["Heading2"]),
    ]
    table_data = [["Área", "Prom.", "V", "A", "R", "Pend."]]
    for area in report.areas:
        table_data.append(
            [
                Paragraph(escape(area.name), small),
                f"{area.average:.1f}" if area.average is not None else "—",
                *[str(area.distribution[level]) for level in LIGHTS],
            ]
        )
    table = Table(
        table_data,
        colWidths=[8.5 * cm, 1.8 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.8 * cm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1f2")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.3 * cm)])
    story.append(
        Paragraph(
            "Prom. = promedio de resultados completos (0–100); V = verde; "
            "A = amarillo; R = rojo; Pend. = sin resultado completo.",
            small,
        )
    )
    story.extend(
        [Spacer(1, 0.4 * cm), Paragraph("Casos abiertos por nivel", styles["Heading2"])]
    )
    for level, count in report.open_cases_by_level.items():
        story.append(Paragraph(f"{escape(level)}: {count}", normal))
    story.extend(
        [
            Spacer(1, 0.4 * cm),
            Paragraph("Áreas para iniciar la tutoría", styles["Heading2"]),
        ]
    )
    if report.focus_areas:
        for area in report.focus_areas:
            story.append(
                Paragraph(
                    f"{escape(area.name)}: {area.attention_count} alumnos "
                    "en amarillo o rojo.",
                    normal,
                )
            )
    else:
        story.append(Paragraph("No hay áreas con semáforo amarillo o rojo.", normal))
    story.extend(
        [
            Spacer(1, 0.5 * cm),
            Paragraph(
                "Este resumen muestra tendencias del grupo, no describe a cada "
                "estudiante ni constituye un diagnóstico. Documento confidencial "
                "para el tutor del grupo; compartir sólo por canales institucionales.",
                small,
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
