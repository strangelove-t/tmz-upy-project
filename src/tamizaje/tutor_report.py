"""Expediente para tutor con la identidad UPY del reporte del alumno.

Sólo recibe los campos de la lista blanca que entrega
``reports.build_report_data``; nunca consulta la base de datos.
"""

from datetime import datetime
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
    BRAND,
    BRAND_SOFT,
    HEADER_ROW,
    LEVELS,
    LINE,
    PENDING,
    RED,
    Dot,
    ScoreBar,
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
from tamizaje.sensitive_summary import SensitiveSummary

FOOTER = "Confidencial · Uso exclusivo de Orientación y Tutorías."


def _level(line) -> str:
    return line.traffic_light if line.traffic_light in LEVELS else PENDING


def _ordered(lines) -> list:
    """Primero lo que requiere atención, igual que el reporte del alumno."""
    return sorted(lines, key=lambda line: (LEVELS[_level(line)][2], line.area_code))


def _area_table(lines) -> Table:
    name_style = style("area", fontName="Lato-Bold", leading=13)
    small = small_style()
    note = style("note", fontSize=9, leading=11.2)
    rows = [table_header(["", "Área e interpretación", "", "Cifra", "Semáforo"])]
    for line in lines:
        level = _level(line)
        color, background, _ = LEVELS[level]
        score = line.score if level != PENDING else None
        rows.append([
            Dot(color),
            [Paragraph(escape(line.area_name), name_style),
             Paragraph(escape(line.description), small),
             Paragraph(escape(line.interpretation), note)],
            ScoreBar(score, color, width=3.0 * cm),
            score_cell(score, color),
            pill(level if level != PENDING else "Sin información", color,
                 background),
        ])
    table = Table(
        rows,
        colWidths=[0.6 * cm, 8.6 * cm, 3.1 * cm, 2.2 * cm, 3.1 * cm],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        *HEADER_ROW,
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
        ("LEFTPADDING", (4, 0), (4, -1), 10),
    ]))
    return table


def _sensitive_block(summary: SensitiveSummary) -> list:
    body = body_style()
    small = small_style()
    color, background = RED
    rows = [
        [Table(
            [[Paragraph("Condiciones y apoyos declarados",
                        style("st", fontName="Lato-Bold", fontSize=12,
                              leading=15, textColor=BRAND)),
              pill("Confidencial", color, background)]],
            colWidths=[13.4 * cm, 3.0 * cm],
            style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                   ("LEFTPADDING", (0, 0), (-1, -1), 0),
                   ("ALIGN", (1, 0), (1, 0), "RIGHT")],
        )],
        [Paragraph(
            "Lo declaró el propio alumno. No modifica la prioridad ni es una "
            "valoración de la universidad. Uso exclusivo de Orientación y "
            "Tutorías.",
            small,
        )],
    ]
    if summary.requires_review:
        rows.append([Paragraph(
            "<b>Hay respuestas que requieren revisión por posible "
            "inconsistencia.</b>", small)])
    muted = small.textColor.hexval()
    for category in summary.categories:
        rows.append([[
            Spacer(1, 4),
            Paragraph(f"<b>{escape(category.label)}</b>", body),
            Paragraph(
                "<br/>".join(
                    f'<font color="{muted}">{escape(label)}:</font> {escape(value)}'
                    for label, value in category.fields
                ),
                style("sf", fontSize=9.5, leading=13),
            ),
        ]])
    return [CondPageBreak(5 * cm), KeepTogether(card(rows, BRAND, BRAND_SOFT,
                                                     radius=10, padding=14))]


def render_tutor_pdf(data: dict, title: str) -> bytes:
    body = body_style()
    small = small_style()
    heading = heading_style()
    lines = _ordered(data.get("areas", []))
    generated = datetime.strptime(data["generated_at"], "%Y-%m-%d")

    story: list = [
        header(
            title,
            f"<b>{escape(data['student_name'])}</b> · {escape(data['career'])} · "
            f"Grupo {escape(data['group_name'])} · {generated:%d/%m/%Y}",
        ),
        Spacer(1, 10),
    ]
    if data.get("introduction"):
        story.append(Paragraph(escape(data["introduction"]), body))

    if lines:
        counts = {level: sum(_level(line) == level for line in lines)
                  for level in ("Verde", "Amarillo", "Rojo")}
        names = {"Verde": "en verde", "Amarillo": "en amarillo", "Rojo": "en rojo"}
        story += [
            Paragraph("Resumen", heading),
            stat_cards([
                (str(counts[level]),
                 f"{'área' if counts[level] == 1 else 'áreas'} · "
                 f"<b>{names[level]}</b>",
                 LEVELS[level][:2])
                for level in ("Verde", "Amarillo", "Rojo")
            ]),
        ]

    if data.get("traffic_light_legend"):
        story += [
            Paragraph("Cómo leer el semáforo", heading),
            legend([
                (label, explanation,
                 LEVELS.get(label, LEVELS[PENDING])[0])
                for label, explanation in data["traffic_light_legend"].items()
            ]),
        ]

    if lines:
        story += [
            CondPageBreak(6 * cm),
            Paragraph("Resultados por área", heading),
            Paragraph(
                "Cifra de 0 a 100 por área: entre más alta, más recursos "
                "favorables. Primero aparecen las áreas que conviene atender.",
                small,
            ),
            Spacer(1, 4),
            _area_table(lines),
        ]

    recommendations = dict(data.get("recommendations", []))
    if recommendations:
        level_by_area = {line.area_name: _level(line) for line in lines}
        focus = [line for line in lines
                 if _level(line) in ("Rojo", "Amarillo")
                 and line.area_name in recommendations]
        strengths = [line for line in lines
                     if _level(line) == "Verde" and line.area_name in recommendations]
        others = [name for name in recommendations if name not in level_by_area]
        story += [CondPageBreak(5 * cm),
                  Paragraph("Acciones sugeridas para la tutoría", heading)]
        for line in focus:
            color, background, _ = LEVELS[_level(line)]
            story += [
                KeepTogether(card([
                    [Paragraph(f"<b>{escape(line.area_name)}</b>",
                               style("rt", fontSize=11, leading=14,
                                     textColor=color))],
                    [Paragraph(escape(recommendations[line.area_name]), body)],
                ], color, background)),
                Spacer(1, 7),
            ]
        if not focus:
            story.append(Paragraph(
                "Ninguna área está en amarillo o rojo.", small))
        if strengths or others:
            story.append(Paragraph("Fortalezas para reconocer",
                                   style("h3", fontName="Lato-Bold", fontSize=11.5,
                                         leading=15, spaceBefore=6, spaceAfter=3,
                                         textColor=BRAND)))
            for name in [line.area_name for line in strengths] + others:
                story.append(Paragraph(
                    f"<b>{escape(name)}:</b> {escape(recommendations[name])}",
                    style("sr", fontSize=9.5, leading=12.5, spaceAfter=3),
                ))

    sensitive: SensitiveSummary | None = data.get("sensitive_summary")
    if sensitive is not None and sensitive.has_sensitive_declaration:
        story += [Spacer(1, 10), *_sensitive_block(sensitive)]

    if data.get("disclaimer"):
        story += [Spacer(1, 10), Paragraph(escape(data["disclaimer"]), small)]
    return build_pdf(story, title, FOOTER)
