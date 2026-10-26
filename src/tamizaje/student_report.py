"""Presentación del reporte del alumno: identidad UPY, resumen y acciones.

Sólo recibe los campos de la lista blanca que entrega
``reports.build_report_data``; nunca consulta la base de datos.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape

from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from tamizaje.pdf_brand import (
    ASSETS_DIR,
    BRAND,
    BRAND_SOFT,
    LEVELS,
    LINE,
    PENDING,
    Dot,
    ScoreBar,
    body_style,
    build_pdf,
    card,
    header,
    heading_style,
    notes_card,
    pill,
    register_fonts,
    score_cell,
    score_text,
    small_style,
    stat_cards,
    style,
)

__all__ = ["ASSETS_DIR", "build_student_view", "contact_line", "join_area_names",
           "render_student_pdf", "scale_note", "score_text", "student_area_note",
           "STRENGTHS_SUFFIX"]

STRENGTHS_SUFFIX = (
    "Son recursos que te ayudarán durante la carrera: aprovéchalos y compártelos "
    "con tus compañeros."
)


@dataclass(frozen=True)
class StudentAreaView:
    area_code: str
    area_name: str
    description: str
    score: Decimal | None
    level: str
    label: str


@dataclass(frozen=True)
class StudentReportView:
    areas: tuple[StudentAreaView, ...]
    counts: dict[str, int]
    focus: tuple[tuple[str, str, str], ...]  # (área, recomendación, nivel)
    strengths: list[str]
    missing: list[str]


def scale_note(scale: dict | None) -> str:
    if not scale:
        return "Entre más alta la cifra, mayor fortaleza."
    green, yellow = scale["green_min"], scale["yellow_min"]
    return (
        f"Fortaleza desde {green}, seguimiento de {yellow} a {green - 1} y "
        f"atención por debajo de {yellow}."
    )


def student_area_note(scale: dict | None) -> str:
    return (
        "Cada área tiene una cifra de 0 a 100 y una barra: entre más alta, "
        f"más fortaleza. {scale_note(scale)} Primero aparecen las áreas que "
        "conviene atender."
    )


def contact_line(data: dict) -> str | None:
    """El contacto de Orientación sólo se imprime cuando está configurado."""
    contact = str(data.get("contact") or "").strip()
    return contact or None


def build_student_view(data: dict, labels: dict[str, str]) -> StudentReportView:
    """Mismo modelo para la vista previa y el PDF."""
    areas = []
    for line in data["areas"]:
        level = line.traffic_light if line.traffic_light in LEVELS else PENDING
        areas.append(
            StudentAreaView(
                area_code=line.area_code,
                area_name=line.area_name,
                description=line.description,
                score=line.score if level != PENDING else None,
                level=level,
                label=labels[level],
            )
        )
    areas.sort(key=lambda item: (LEVELS[item.level][2], item.area_code))
    recommendation_by_area = {
        line.area_name: line.recommendation for line in data["areas"]
    }
    return StudentReportView(
        areas=tuple(areas),
        counts={
            level: sum(item.level == level for item in areas)
            for level in ("Verde", "Amarillo", "Rojo")
        },
        focus=tuple(
            (item.area_name, recommendation_by_area[item.area_name], item.level)
            for item in areas
            if item.level in ("Rojo", "Amarillo")
            and recommendation_by_area.get(item.area_name)
        ),
        strengths=[item.area_name for item in areas if item.level == "Verde"],
        missing=[item.area_name for item in areas if item.level == PENDING],
    )


# --- Renderizado --------------------------------------------------------------
def _summary(view: StudentReportView, labels: dict[str, str]) -> Table:
    items = []
    for level in ("Verde", "Amarillo", "Rojo"):
        color, background, _ = LEVELS[level]
        count = view.counts[level]
        items.append((
            str(count),
            f"{'área' if count == 1 else 'áreas'} · "
            f"<b>{escape(labels[level].lower())}</b>",
            (color, background),
        ))
    return stat_cards(items)


def _area_table(view: StudentReportView) -> Table:
    name_style = style("area", fontName="Lato-Bold", leading=13)
    small = small_style()
    rows = []
    for item in view.areas:
        color, background, _ = LEVELS[item.level]
        rows.append([
            Dot(color),
            [Paragraph(escape(item.area_name), name_style),
             Paragraph(escape(item.description), small)],
            ScoreBar(item.score, color),
            score_cell(item.score, color),
            pill(item.label, color, background),
        ])
    table = Table(
        rows,
        colWidths=[0.6 * cm, 8.0 * cm, 3.5 * cm, 2.3 * cm, 3.2 * cm],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
        ("LEFTPADDING", (4, 0), (4, -1), 10),
    ]))
    return table


def join_area_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def render_student_pdf(data: dict, title: str) -> bytes:
    register_fonts()
    labels = data["student_labels"]
    view = build_student_view(data, labels)
    body = body_style()
    small = small_style()
    heading = heading_style()
    generated = datetime.strptime(data["generated_at"], "%Y-%m-%d")

    story: list = [
        header(
            title,
            f"<b>{escape(data['student_name'])}</b> · {escape(data['career'])} · "
            f"Grupo {escape(data['group_name'])} · {generated:%d/%m/%Y}",
        ),
        Spacer(1, 10),
        Paragraph(escape(data["student_introduction"]), body),
        Spacer(1, 4),
        Paragraph("Tu resumen", heading),
        _summary(view, labels),
        Spacer(1, 6),
        Paragraph("Tus resultados por área", heading),
        Paragraph(student_area_note(data.get("score_scale")), small),
        Spacer(1, 4),
        _area_table(view),
    ]

    if view.focus:
        story += [CondPageBreak(6 * cm), Paragraph("Qué te recomendamos", heading)]
        for area_name, recommendation, level in view.focus:
            color, background, _ = LEVELS[level]
            story += [
                KeepTogether(card([
                    [Paragraph(f"<b>{escape(area_name)}</b>",
                               style("rt", fontSize=11, leading=14,
                                      textColor=color))],
                    [Paragraph(escape(recommendation), body)],
                ], color, background)),
                Spacer(1, 7),
            ]

    if view.strengths:
        story += [
            Paragraph("Tus fortalezas", heading),
            Paragraph(
                f"Destacas en <b>{escape(join_area_names(view.strengths))}</b>. "
                f"{STRENGTHS_SUFFIX}",
                body,
            ),
        ]
    if view.missing:
        story += [Spacer(1, 6), Paragraph(
            "No tuvimos información suficiente para interpretar "
            f"<b>{escape(', '.join(view.missing))}</b>. Si quieres, platícalo con "
            "Orientación y Tutorías.",
            small,
        )]

    if data.get("notes"):
        story += [Spacer(1, 12),
                  notes_card("Mensaje de Orientación y Tutorías", data["notes"])]

    contact_rows = [
        Paragraph("¿Con quién puedes hablar?",
                  style("ct", fontName="Lato-Bold", fontSize=12, leading=15,
                         textColor=BRAND)),
        Spacer(1, 4),
        Paragraph(
            "".join(f"• {escape(item)}<br/>" for item in data.get("resources", [])),
            body,
        ),
    ]
    if contact := contact_line(data):
        contact_rows += [
            Spacer(1, 4),
            Paragraph(f"<b>Orientación y Tutorías:</b> {escape(contact)}", body),
        ]
    story += [
        Spacer(1, 12),
        KeepTogether(card([[contact_rows]], BRAND, BRAND_SOFT, radius=10,
                           padding=14)),
        Spacer(1, 10),
        Paragraph(escape(data["disclaimer"]), small),
    ]

    return build_pdf(
        story, title,
        "Confidencial · Este reporte orienta apoyos; no es un diagnóstico.",
    )
