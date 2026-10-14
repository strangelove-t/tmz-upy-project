"""Presentación del reporte del alumno: identidad UPY, resumen y acciones.

Sólo recibe los campos de la lista blanca que entrega
``reports.build_report_data``; nunca consulta la base de datos.
"""

import io
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import cache
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
CONTENT_WIDTH = 17.6 * cm  # carta con márgenes de 2 cm

# Paleta institucional. El naranja es sólo acento sobre morado: sobre blanco
# no alcanza contraste (2:1) y se confundiría con "Dar seguimiento".
INK = colors.HexColor("#1B1319")
MUTED = colors.HexColor("#5E5662")
LINE = colors.HexColor("#E7E1EA")
SOFT = colors.HexColor("#F6F3F7")
BRAND = colors.HexColor("#5B0A8A")
BRAND_SOFT = colors.HexColor("#F3EAF8")
BRAND_TINT = colors.HexColor("#E9D7F3")
ACCENT = colors.HexColor("#FDA20C")

# Semáforo: (color, fondo suave, orden). Independiente de la marca.
PENDING = "Pendiente de revisión"
LEVELS = {
    "Rojo": (colors.HexColor("#C62828"), colors.HexColor("#FDECEC"), 0),
    "Amarillo": (colors.HexColor("#A86B00"), colors.HexColor("#FFF4DB"), 1),
    "Verde": (colors.HexColor("#2E7D32"), colors.HexColor("#E8F4EA"), 2),
    PENDING: (MUTED, SOFT, 3),
}


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


def score_text(score: Decimal | None) -> str:
    """Parte entera: nunca cruza un umbral (69.6 se muestra 69, amarillo)."""
    return "—" if score is None else str(math.floor(score))


def scale_note(scale: dict | None) -> str:
    if not scale:
        return "Entre más alta la cifra, mayor fortaleza."
    green, yellow = scale["green_min"], scale["yellow_min"]
    return (
        f"Fortaleza desde {green}, seguimiento de {yellow} a {green - 1} y "
        f"atención por debajo de {yellow}."
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
@cache
def _register_fonts() -> None:
    fonts = ASSETS_DIR / "fonts"
    for name in ("Lato-Regular", "Lato-Bold", "Lato-Black"):
        pdfmetrics.registerFont(TTFont(name, str(fonts / f"{name}.ttf")))
    pdfmetrics.registerFontFamily(
        "Lato-Regular",
        normal="Lato-Regular",
        bold="Lato-Bold",
        italic="Lato-Regular",
        boldItalic="Lato-Bold",
    )


def _style(name: str, **overrides) -> ParagraphStyle:
    values = dict(fontName="Lato-Regular", fontSize=10.5, leading=14.5,
                  textColor=INK)
    values.update(overrides)
    return ParagraphStyle(name, **values)


class _Dot(Flowable):
    def __init__(self, color, size: float = 9) -> None:
        super().__init__()
        self.color, self.size = color, size
        self.width = self.height = size

    def draw(self) -> None:
        radius = self.size / 2
        self.canv.setFillColor(self.color)
        self.canv.circle(radius, radius, radius, stroke=0, fill=1)


class _ScoreBar(Flowable):
    def __init__(self, score: Decimal | None, color) -> None:
        super().__init__()
        self.score, self.color = score, color
        self.width, self.height = 3.4 * cm, 7

    def draw(self) -> None:
        radius = self.height / 2
        self.canv.setFillColor(LINE)
        self.canv.roundRect(0, 0, self.width, self.height, radius, stroke=0, fill=1)
        if self.score is None:
            return
        filled = max(self.height, self.width * float(self.score) / 100)
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, filled, self.height, radius, stroke=0, fill=1)


def _card(rows, color, background, *, radius: int = 8, padding: int = 12):
    table = Table(rows, colWidths=[CONTENT_WIDTH], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("ROUNDEDCORNERS", [radius] * 4),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (0, 0), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
    ]))
    return table


def _pill(text: str, color, background) -> Table:
    table = Table([[Paragraph(
        f"<b>{escape(text)}</b>",
        _style("pill", fontSize=8.5, leading=10, textColor=color),
    )]])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("ROUNDEDCORNERS", [6] * 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _draw_page(canvas, document) -> None:
    width, height = letter
    canvas.saveState()
    canvas.setFillColor(BRAND)
    canvas.rect(0, height - 0.55 * cm, width, 0.55 * cm, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, height - 0.70 * cm, width, 0.15 * cm, stroke=0, fill=1)
    canvas.setFont("Lato-Regular", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        2 * cm, 1.2 * cm,
        "Confidencial · Este reporte orienta apoyos; no es un diagnóstico.",
    )
    canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {document.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.55 * cm, width - 2 * cm, 1.55 * cm)
    canvas.restoreState()


def _header(data: dict, title: str) -> Table:
    generated = datetime.strptime(data["generated_at"], "%Y-%m-%d")
    text = [
        Paragraph(
            "UNIVERSIDAD POLITÉCNICA DE YUCATÁN · ORIENTACIÓN Y TUTORÍAS",
            _style("kicker", fontName="Lato-Bold", fontSize=8, leading=10,
                   textColor=ACCENT),
        ),
        Spacer(1, 3),
        Paragraph(escape(title), _style("h1", fontName="Lato-Black", fontSize=22,
                                        leading=26, textColor=colors.white)),
        Spacer(1, 4),
        Paragraph(
            f"<b>{escape(data['student_name'])}</b> · {escape(data['career'])} · "
            f"Grupo {escape(data['group_name'])} · {generated:%d/%m/%Y}",
            _style("who", fontSize=10, leading=13, textColor=BRAND_TINT),
        ),
    ]
    logo = Image(str(ASSETS_DIR / "logo_upy.png"), width=1.8 * cm,
                 height=1.8 * cm, mask="auto")
    band = Table([[text, logo]], colWidths=[15.1 * cm, 2.5 * cm])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND),
        ("ROUNDEDCORNERS", [10] * 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (0, 0), 16),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return band


def _summary(view: StudentReportView, labels: dict[str, str]) -> Table:
    cells = []
    for level in ("Verde", "Amarillo", "Rojo"):
        color, background, _ = LEVELS[level]
        count = view.counts[level]
        cell = Table([
            [Paragraph(str(count), _style(f"n{level}", fontName="Lato-Black",
                                          fontSize=24, leading=26,
                                          textColor=color))],
            [Paragraph(
                f"{'área' if count == 1 else 'áreas'} · "
                f"<b>{escape(labels[level].lower())}</b>",
                _style("count", fontSize=9.5, leading=12),
            )],
        ], colWidths=[5.6 * cm])
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("LINEBEFORE", (0, 0), (0, -1), 3, color),
            ("ROUNDEDCORNERS", [8] * 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (0, 0), 9),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ]))
        cells.append(cell)
    row = Table([cells], colWidths=[CONTENT_WIDTH / 3] * 3, hAlign="LEFT")
    row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return row


def _area_table(view: StudentReportView) -> Table:
    name_style = _style("area", fontName="Lato-Bold", leading=13)
    small = _style("small", fontSize=9, leading=11.2, textColor=MUTED)
    rows = []
    for item in view.areas:
        color, background, _ = LEVELS[item.level]
        suffix = "" if item.score is None else " /100"
        rows.append([
            _Dot(color),
            [Paragraph(escape(item.area_name), name_style),
             Paragraph(escape(item.description), small)],
            _ScoreBar(item.score, color),
            Paragraph(
                f'<font name="Lato-Black" size="13" color="{color.hexval()}">'
                f"{score_text(item.score)}</font>"
                f'<font size="8" color="{MUTED.hexval()}">{suffix}</font>',
                _style("score", alignment=2, leading=14),
            ),
            _pill(item.label, color, background),
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


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def render_student_pdf(data: dict, title: str) -> bytes:
    _register_fonts()
    labels = data["student_labels"]
    view = build_student_view(data, labels)
    body = _style("body")
    small = _style("small", fontSize=9, leading=11.2, textColor=MUTED)
    heading = _style("h2", fontName="Lato-Bold", fontSize=14, leading=18,
                     spaceBefore=8, spaceAfter=5, textColor=BRAND)

    story: list = [
        _header(data, title),
        Spacer(1, 10),
        Paragraph(escape(data["student_introduction"]), body),
        Spacer(1, 4),
        Paragraph("Tu resumen", heading),
        _summary(view, labels),
        Spacer(1, 6),
        Paragraph("Tus resultados por área", heading),
        Paragraph(
            "Cada área tiene una cifra de 0 a 100 y una barra: entre más alta, "
            f"más fortaleza. {scale_note(data.get('score_scale'))} Primero "
            "aparecen las áreas que conviene atender.",
            small,
        ),
        Spacer(1, 4),
        _area_table(view),
    ]

    if view.focus:
        story += [CondPageBreak(6 * cm), Paragraph("Qué te recomendamos", heading)]
        for area_name, recommendation, level in view.focus:
            color, background, _ = LEVELS[level]
            story += [
                KeepTogether(_card([
                    [Paragraph(f"<b>{escape(area_name)}</b>",
                               _style("rt", fontSize=11, leading=14,
                                      textColor=color))],
                    [Paragraph(escape(recommendation), body)],
                ], color, background)),
                Spacer(1, 7),
            ]

    if view.strengths:
        story += [
            Paragraph("Tus fortalezas", heading),
            Paragraph(
                f"Destacas en <b>{escape(_join(view.strengths))}</b>. Son recursos "
                "que te ayudarán durante la carrera: aprovéchalos y compártelos "
                "con tus compañeros.",
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

    contact_rows = [
        Paragraph("¿Con quién puedes hablar?",
                  _style("ct", fontName="Lato-Bold", fontSize=12, leading=15,
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
        KeepTogether(_card([[contact_rows]], BRAND, BRAND_SOFT, radius=10,
                           padding=14)),
        Spacer(1, 10),
        Paragraph(escape(data["disclaimer"]), small),
    ]

    buffer = io.BytesIO()
    document = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.4 * cm,
        bottomMargin=2 * cm,
        title=title,
        invariant=1,
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width,
                  document.height, leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    document.addPageTemplates([PageTemplate(frames=[frame], onPage=_draw_page)])
    document.build(story)
    return buffer.getvalue()
