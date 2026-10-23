"""Informe para tutoría grupal con lista mínima de atención confidencial."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from tamizaje.models import EngineConfig
from tamizaje.pdf_brand import (
    AMBER,
    BRAND,
    BRAND_SOFT,
    GREEN,
    HEADER_ROW,
    LEVELS,
    LINE,
    MUTED,
    PENDING,
    RED,
    SOFT,
    Dot,
    ScoreBar,
    attention_colors,
    body_style,
    build_pdf,
    card,
    header,
    heading_style,
    legend,
    pill,
    score_cell,
    small_style,
    stat_cards,
    style,
    table_header,
)
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
    level: str = PENDING  # color del promedio según los umbrales del área

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
    attention_levels: tuple[str, ...]
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


def _average_level(average: Decimal | None, definition) -> str:
    if average is None:
        return PENDING
    if average >= definition.green_min:
        return "Verde"
    if average >= definition.yellow_min:
        return "Amarillo"
    return "Rojo"


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
        average = sum(scores) / len(scores) if scores else None
        summaries.append(
            GroupAreaSummary(
                code=definition.area_code,
                name=definition.area_name,
                description=content.areas[definition.area_code],
                average=average,
                complete_count=len(scores),
                distribution=distribution,
                level=_average_level(average, definition),
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
        attention_levels=tuple(engine.alerts.levels),
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


FOOTER = (
    "Confidencial · Contiene nombres de alumnos. Uso exclusivo del tutor del grupo."
)


def _count(number: int, color, count_style) -> Paragraph:
    """Los ceros van en gris para que sólo resalte lo que hay que atender."""
    shade = color if number else MUTED
    return Paragraph(f'<font color="{shade.hexval()}">{number}</font>', count_style)


def _areas_table(report: GroupReport) -> Table:
    name_style = style("area", fontName="Lato-Bold", leading=13)
    small = small_style()
    count_style = style("cnt", fontName="Lato-Bold", fontSize=10.5, leading=13,
                        alignment=1)
    rows = [table_header(["", "Área y qué observa", "Promedio del grupo", "",
                          "Verde", "Amarillo", "Rojo", "Sin dato"])]
    for area in report.areas:
        color, _, _ = LEVELS[area.level]
        rows.append([
            Dot(color),
            [Paragraph(escape(area.name), name_style),
             Paragraph(escape(area.description), small)],
            ScoreBar(area.average, color, width=2.4 * cm),
            score_cell(area.average, color),
            *[
                _count(area.distribution[key], LEVELS[light][0], count_style)
                for key, light in (("Verde", "Verde"), ("Amarillo", "Amarillo"),
                                   ("Rojo", "Rojo"), ("Pendiente", PENDING))
            ],
        ])
    table = Table(
        rows,
        colWidths=[0.6 * cm, 6.6 * cm, 2.6 * cm, 2.0 * cm,
                   1.3 * cm, 1.9 * cm, 1.2 * cm, 1.4 * cm],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        *HEADER_ROW,
        ("SPAN", (2, 0), (3, 0)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
    ]))
    return table


def _roster(report: GroupReport) -> Table:
    name_style = style("rs", fontSize=9.5, leading=12)
    centered = style("rc", fontSize=10, leading=12, alignment=1)
    rows = [table_header(["#", "Alumno", "Nivel", "Alertas", "Pidió contacto"])]
    for index, student in enumerate(report.students, start=1):
        color, background = attention_colors(student.level, report.attention_levels)
        rows.append([
            Paragraph(str(index), style("ix", fontSize=9.5, textColor=MUTED)),
            Paragraph(f"<b>{escape(student.name)}</b>", name_style),
            pill(student.level, color, background),
            Paragraph(str(student.alert_count), centered),
            Paragraph(
                f'<font color="{RED[0].hexval()}"><b>Sí</b></font>'
                if student.requested_contact
                else "No",
                centered,
            ),
        ])
    table = Table(
        rows,
        colWidths=[0.9 * cm, 7.4 * cm, 4.6 * cm, 1.8 * cm, 2.9 * cm],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        *HEADER_ROW,
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _focus_colors(area: GroupAreaSummary) -> tuple:
    """Un área llega aquí por tener alumnos en amarillo o rojo, aunque su
    promedio sea verde: se pinta al menos de amarillo."""
    return RED if area.level == "Rojo" else AMBER


def render_group_pdf(report: GroupReport) -> bytes:
    body = body_style()
    small = small_style()
    heading = heading_style()
    title = f"Grupo {report.group_name}"
    requested = sum(student.requested_contact for student in report.students)
    accompaniment = len(report.students)

    story: list = [
        header(
            title,
            f"Informe para el tutor del grupo · <b>{escape(report.career)}</b> · "
            f"{report.generated_at:%d/%m/%Y %H:%M}",
        ),
        Spacer(1, 10),
        Paragraph(
            "Este informe resume las respuestas del grupo para orientar "
            "conversaciones y apoyos. No califica a cada alumno ni constituye un "
            "diagnóstico.",
            body,
        ),
        Paragraph("Resumen del grupo", heading),
        stat_cards([
            (str(report.student_count), "alumnos <b>evaluados</b>",
             (BRAND, BRAND_SOFT)),
            (str(accompaniment),
             f"{'requiere' if accompaniment == 1 else 'requieren'} "
             "<b>acompañamiento</b>",
             RED if accompaniment else GREEN),
            (str(requested),
             f"{'pidió' if requested == 1 else 'pidieron'} <b>contacto</b>",
             AMBER if requested else GREEN),
        ]),
        Paragraph("Cómo leer los resultados", heading),
        legend([
            (label, explanation, LEVELS.get(label, LEVELS[PENDING])[0])
            for label, explanation in report.traffic_light_legend.items()
        ]),
        Spacer(1, 6),
        Paragraph(
            "<b>Niveles de atención</b> · casos abiertos en el grupo",
            style("lv", fontSize=10.5, leading=14, textColor=BRAND),
        ),
        Spacer(1, 2),
        legend([
            (f"{level} ({report.open_cases_by_level[level]})", explanation,
             attention_colors(level, report.attention_levels)[0])
            for level, explanation in report.level_explanations.items()
        ]),
        CondPageBreak(7 * cm),
        Paragraph("Áreas del grupo", heading),
        Paragraph(
            "Promedio de 0 a 100: entre más alto, más recursos favorables. Las "
            "columnas de color cuentan alumnos, no diagnósticos. «Sin dato» "
            "significa que no hubo información suficiente para interpretar el "
            "área.",
            small,
        ),
        Spacer(1, 4),
        _areas_table(report),
        CondPageBreak(5 * cm),
        Paragraph("Áreas para iniciar la conversación", heading),
    ]
    if report.focus_areas:
        for area in report.focus_areas:
            color, background = _focus_colors(area)
            plural = "alumno" if area.attention_count == 1 else "alumnos"
            story += [
                KeepTogether(card([
                    [Paragraph(f"<b>{escape(area.name)}</b>",
                               style("ft", fontSize=11, leading=14,
                                     textColor=color))],
                    [Paragraph(
                        f"<b>{area.attention_count} {plural}</b> en amarillo o "
                        f"rojo. {escape(area.description)}",
                        body,
                    )],
                ], color, background)),
                Spacer(1, 7),
            ]
    else:
        story.append(Paragraph("No hay áreas con semáforo amarillo o rojo.", small))

    story += [
        CondPageBreak(5 * cm),
        Paragraph("Alumnos que requieren acompañamiento", heading),
        Paragraph(
            "Sólo aparecen alumnos con una atención abierta, en el mismo orden "
            "que usa Orientación y Tutorías: solicitud de contacto, nivel, áreas "
            "que necesitan apoyo y número de alertas. Una alerta es una señal para "
            "conversar, no un diagnóstico. Puede haber una atención abierta aunque "
            "las áreas estén en verde. «Pidió contacto» indica que el alumno "
            "solicitó hablar con Orientación.",
            small,
        ),
        Spacer(1, 4),
        _roster(report) if report.students
        else Paragraph("No hay alumnos con atención abierta.", small),
        Spacer(1, 12),
        Paragraph(
            "Documento confidencial con nombres de alumnos. Uso exclusivo del "
            "tutor del grupo; compartir sólo por canales institucionales. Para "
            "conocer el motivo o acordar apoyos, consultar a Orientación y "
            "Tutorías.",
            small,
        ),
    ]
    return build_pdf(story, title, FOOTER)
