"""Informe para tutoría grupal con lista mínima de atención confidencial."""

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

from tamizaje.models import EngineConfig
from tamizaje.reports import load_report_content, safe_filename_fragment
from tamizaje.repository import CLOSED_STATUS, cases_frame

LIGHTS = ("Verde", "Amarillo", "Rojo", "Pendiente")


class GroupReportError(ValueError):
    """El grupo no cumple el umbral de confidencialidad."""


@dataclass(frozen=True)
class GroupAreaSummary:
    code: str
    name: str
    description: str
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
    areas: tuple[GroupAreaSummary, ...]
    open_cases_by_level: dict[str, int]
    traffic_light_legend: dict[str, str]
    level_explanations: dict[str, str]
    students: tuple["GroupStudent", ...]

    @property
    def focus_areas(self) -> tuple[GroupAreaSummary, ...]:
        ranked = sorted(self.areas, key=lambda area: (-area.attention_count, area.code))
        return tuple(area for area in ranked if area.attention_count > 0)[:3]


@dataclass(frozen=True)
class GroupStudent:
    name: str
    level: str
    alert_count: int
    requested_contact: bool


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

    content = load_report_content(engine)
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
                description=content.areas[definition.area_code],
                average=sum(scores) / len(scores) if scores else None,
                complete_count=len(scores),
                distribution=distribution,
            )
        )

    cases = cases_frame(connection, engine)
    cases = cases[
        (cases["career"] == career)
        & (cases["group_name"] == group_name)
        & (cases["case_status"] != CLOSED_STATUS)
    ]
    counts = dict.fromkeys(engine.alerts.levels, 0)
    for level, number in cases["case_level"].value_counts().items():
        if level in counts:
            counts[level] = int(number)
    students = tuple(
        GroupStudent(
            name=row.student_name,
            level=row.case_level,
            alert_count=int(row.total_alert_count),
            requested_contact=bool(row.requested_contact),
        )
        for row in cases.itertuples()
    )
    return GroupReport(
        career=career,
        group_name=group_name,
        generated_at=datetime.now(engine.report_timezone),
        student_count=count,
        areas=tuple(summaries),
        open_cases_by_level=counts,
        traffic_light_legend=content.traffic_light_legend,
        level_explanations=content.group_level_explanations,
        students=students,
    )


def group_report_filename(report: GroupReport) -> str:
    key = f"{report.career}\0{report.group_name}".encode()
    digest = hashlib.sha256(key).hexdigest()[:8]
    group = safe_filename_fragment(report.group_name, max_length=64)
    career = safe_filename_fragment(report.career, max_length=64)
    return f"grupo_{group}_{career}_{digest}_{report.generated_at:%Y%m%d}.pdf"


def render_group_pdf(report: GroupReport) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm
    )
    styles = getSampleStyleSheet()
    normal = styles["BodyText"]
    small = ParagraphStyle("GroupSmall", parent=normal, fontSize=8.5, leading=11)
    heading = ParagraphStyle(
        "GroupHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0B6E75"),
    )
    table_header = colors.HexColor("#e9f1f2")
    story = [
        Paragraph(f"Grupo {escape(report.group_name)}", styles["Title"]),
        Paragraph(
            f"Informe para el tutor del grupo · {escape(report.career)}",
            normal,
        ),
        Paragraph(f"Generado: {report.generated_at:%d/%m/%Y %H:%M}", normal),
        Spacer(1, 0.35 * cm),
        Paragraph(
            "Este informe resume respuestas del grupo para orientar conversaciones "
            "y apoyos. No califica a cada alumno ni constituye un diagnóstico.",
            normal,
        ),
        Spacer(1, 0.25 * cm),
        Paragraph(
            f"<b>{report.student_count} alumnos evaluados</b> · "
            f"<b>{len(report.students)} requieren acompañamiento</b>",
            normal,
        ),
        Spacer(1, 0.35 * cm),
        Paragraph("Cómo leer los resultados", heading),
    ]
    for light, explanation in report.traffic_light_legend.items():
        story.append(Paragraph(f"<b>{escape(light)}:</b> {escape(explanation)}", small))
    story.extend([Spacer(1, 0.25 * cm), Paragraph("Niveles de atención", heading)])
    for level, explanation in report.level_explanations.items():
        story.append(
            Paragraph(
                f"<b>{escape(level)} ({report.open_cases_by_level[level]}):</b> "
                f"{escape(explanation)}",
                small,
            )
        )
    story.extend(
        [
            Spacer(1, 0.35 * cm),
            Paragraph("Áreas del grupo", heading),
            Paragraph(
                "El promedio va de 0 a 100: un valor mayor indica más recursos "
                "favorables. Los colores cuentan alumnos, no diagnósticos.",
                small,
            ),
            Spacer(1, 0.15 * cm),
        ]
    )
    table_data = [["Área y qué observa", "Prom.", "V", "A", "R", "Sin dato"]]
    for area in report.areas:
        table_data.append(
            [
                Paragraph(
                    f"<b>{escape(area.name)}</b><br/>{escape(area.description)}",
                    small,
                ),
                f"{area.average:.1f}" if area.average is not None else "—",
                *[str(area.distribution[level]) for level in LIGHTS],
            ]
        )
    table = Table(
        table_data,
        colWidths=[8.7 * cm, 1.7 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 2 * cm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), table_header),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.2 * cm)])
    story.append(
        Paragraph(
            "V = verde; A = amarillo; R = rojo. «Sin dato» significa que no "
            "hubo información suficiente para interpretar esa área.",
            small,
        )
    )
    story.extend(
        [
            Spacer(1, 0.35 * cm),
            Paragraph("Áreas para iniciar la conversación", heading),
        ]
    )
    if report.focus_areas:
        for area in report.focus_areas:
            story.append(
                Paragraph(
                    f"{escape(area.name)}: {area.attention_count} alumnos "
                    "en amarillo o rojo.",
                    small,
                )
            )
    else:
        story.append(Paragraph("No hay áreas con semáforo amarillo o rojo.", small))
    story.extend(
        [
            Spacer(1, 0.4 * cm),
            Paragraph("Alumnos que requieren acompañamiento", heading),
            Paragraph(
                "Sólo aparecen alumnos con una atención abierta, en el mismo "
                "orden que usa Orientación y Tutorías: solicitud de contacto, "
                "nivel, áreas que necesitan apoyo y número de alertas. Una "
                "alerta es una señal para conversar, no un diagnóstico. "
                "Puede haber una atención abierta aunque las áreas estén en verde. "
                "«Pidió contacto» indica que el alumno solicitó hablar "
                "con Orientación.",
                small,
            ),
            Spacer(1, 0.15 * cm),
        ]
    )
    if report.students:
        students = [["#", "Alumno", "Nivel", "Alertas", "Pidió contacto"]]
        for index, student in enumerate(report.students, start=1):
            students.append(
                [
                    str(index),
                    Paragraph(escape(student.name), small),
                    Paragraph(escape(student.level), small),
                    str(student.alert_count),
                    "Sí" if student.requested_contact else "No",
                ]
            )
        roster = Table(
            students,
            colWidths=[0.8 * cm, 6.2 * cm, 4.5 * cm, 1.8 * cm, 3 * cm],
            repeatRows=1,
        )
        roster.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), table_header),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(roster)
    else:
        story.append(Paragraph("No hay alumnos con atención abierta.", small))
    story.extend(
        [
            Spacer(1, 0.5 * cm),
            Paragraph(
                "Documento confidencial con nombres de alumnos. Uso exclusivo "
                "del tutor del grupo; compartir sólo por canales institucionales. "
                "Para conocer el motivo o acordar apoyos, consultar a Orientación "
                "y Tutorías.",
                small,
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
