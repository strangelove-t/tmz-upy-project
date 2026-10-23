"""Identidad visual UPY compartida por los PDF: paleta, tipografía y piezas.

Sólo dibuja; no conoce la base de datos ni decide qué datos se publican.
"""

import io
import math
from collections.abc import Sequence
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
    Flowable,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
CONTENT_WIDTH = 17.6 * cm  # carta con márgenes de 2 cm
CARD_GAP = CONTENT_WIDTH / 3 - 5.6 * cm  # separación entre tarjetas

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

RED = (colors.HexColor("#C62828"), colors.HexColor("#FDECEC"))
AMBER = (colors.HexColor("#A86B00"), colors.HexColor("#FFF4DB"))
GREEN = (colors.HexColor("#2E7D32"), colors.HexColor("#E8F4EA"))
NEUTRAL = (MUTED, SOFT)

# Semáforo: (color, fondo suave, orden). Independiente de la marca.
PENDING = "Pendiente de revisión"
LEVELS = {
    "Rojo": (*RED, 0),
    "Amarillo": (*AMBER, 1),
    "Verde": (*GREEN, 2),
    PENDING: (*NEUTRAL, 3),
}
KICKER = "UNIVERSIDAD POLITÉCNICA DE YUCATÁN · ORIENTACIÓN Y TUTORÍAS"


def score_text(score: Decimal | None) -> str:
    """Parte entera: nunca cruza un umbral (69.6 se muestra 69, amarillo)."""
    return "—" if score is None else str(math.floor(score))


def attention_colors(level: str, levels: Sequence[str]) -> tuple:
    """Color de un nivel de atención según su gravedad configurada."""
    if level not in levels:
        return NEUTRAL
    rank = list(levels).index(level)
    if rank == 0:
        return RED
    if rank == len(levels) - 1:
        return AMBER
    return (BRAND, BRAND_SOFT)  # intermedio (revisión manual)


@cache
def register_fonts() -> None:
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


def style(name: str, **overrides) -> ParagraphStyle:
    values = dict(fontName="Lato-Regular", fontSize=10.5, leading=14.5,
                  textColor=INK)
    values.update(overrides)
    return ParagraphStyle(name, **values)


def body_style() -> ParagraphStyle:
    return style("body")


def small_style() -> ParagraphStyle:
    return style("small", fontSize=9, leading=11.2, textColor=MUTED)


def heading_style() -> ParagraphStyle:
    return style("h2", fontName="Lato-Bold", fontSize=14, leading=18,
                 spaceBefore=8, spaceAfter=5, textColor=BRAND)


class Dot(Flowable):
    def __init__(self, color, size: float = 9) -> None:
        super().__init__()
        self.color, self.size = color, size
        self.width = self.height = size

    def draw(self) -> None:
        radius = self.size / 2
        self.canv.setFillColor(self.color)
        self.canv.circle(radius, radius, radius, stroke=0, fill=1)


class ScoreBar(Flowable):
    def __init__(self, score: Decimal | None, color, width: float = 3.4 * cm) -> None:
        super().__init__()
        self.score, self.color = score, color
        self.width, self.height = width, 7

    def draw(self) -> None:
        radius = self.height / 2
        self.canv.setFillColor(LINE)
        self.canv.roundRect(0, 0, self.width, self.height, radius, stroke=0, fill=1)
        if self.score is None:
            return
        filled = max(self.height, self.width * float(self.score) / 100)
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, filled, self.height, radius, stroke=0, fill=1)


def score_cell(score: Decimal | None, color) -> Paragraph:
    suffix = "" if score is None else " /100"
    return Paragraph(
        f'<font name="Lato-Black" size="13" color="{color.hexval()}">'
        f"{score_text(score)}</font>"
        f'<font size="8" color="{MUTED.hexval()}">{suffix}</font>',
        style("score", alignment=2, leading=14),
    )


def card(rows, color, background, *, radius: int = 8, padding: int = 12,
         width: float = CONTENT_WIDTH) -> Table:
    table = Table(rows, colWidths=[width], hAlign="LEFT")
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


def pill(text: str, color, background) -> Table:
    table = Table([[Paragraph(
        f"<b>{escape(text)}</b>",
        style("pill", fontSize=8.5, leading=10, textColor=color),
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


def header(title: str, subtitle: str) -> Table:
    """Banda morada con logo; ``subtitle`` ya viene escapado (admite <b>)."""
    text = [
        Paragraph(KICKER, style("kicker", fontName="Lato-Bold", fontSize=8,
                                leading=10, textColor=ACCENT)),
        Spacer(1, 3),
        Paragraph(escape(title), style("h1", fontName="Lato-Black", fontSize=22,
                                       leading=26, textColor=colors.white)),
        Spacer(1, 4),
        Paragraph(subtitle, style("who", fontSize=10, leading=13,
                                  textColor=BRAND_TINT)),
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


def stat_cards(items: Sequence[tuple[str, str, tuple]]) -> Table:
    """Fila de tarjetas (cifra grande, texto, (color, fondo))."""
    width = CONTENT_WIDTH / len(items)
    cells = []
    for index, (number, caption, (color, background)) in enumerate(items):
        cell = Table([
            [Paragraph(escape(number), style(f"n{index}", fontName="Lato-Black",
                                             fontSize=24, leading=26,
                                             textColor=color))],
            [Paragraph(caption, style("count", fontSize=9.5, leading=12))],
        ], colWidths=[width - CARD_GAP])
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("LINEBEFORE", (0, 0), (0, -1), 3, color),
            ("ROUNDEDCORNERS", [8] * 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (0, 0), 9),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ]))
        cells.append(cell)
    row = Table([cells], colWidths=[width] * len(items), hAlign="LEFT")
    row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return row


def legend(entries: Sequence[tuple[str, str, object]]) -> Table:
    """Lista compacta: punto de color, nombre en negritas y explicación."""
    small = style("legend", fontSize=9.5, leading=12.5)
    table = Table(
        [[Dot(color, 8), Paragraph(f"<b>{escape(name)}:</b> {escape(text)}", small)]
         for name, text, color in entries],
        colWidths=[0.6 * cm, CONTENT_WIDTH - 0.6 * cm],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (0, -1), 4),
        ("TOPPADDING", (1, 0), (1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
    ]))
    return table


def table_header(labels: Sequence[str]) -> list[Paragraph]:
    head = style("th", fontName="Lato-Bold", fontSize=8.5, leading=10.5,
                 textColor=BRAND)
    return [Paragraph(escape(label), head) for label in labels]


HEADER_ROW = [
    ("BACKGROUND", (0, 0), (-1, 0), BRAND_SOFT),
    ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND_TINT),
    ("ROUNDEDCORNERS", [6, 6, 0, 0]),
]


def build_pdf(story: list, title: str, footer: str) -> bytes:
    register_fonts()

    def draw_page(canvas, document) -> None:
        width, height = letter
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, height - 0.55 * cm, width, 0.55 * cm, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, height - 0.70 * cm, width, 0.15 * cm, stroke=0, fill=1)
        canvas.setFont("Lato-Regular", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, 1.2 * cm, footer)
        canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {document.page}")
        canvas.setStrokeColor(LINE)
        canvas.line(2 * cm, 1.55 * cm, width - 2 * cm, 1.55 * cm)
        canvas.restoreState()

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
    document.addPageTemplates([PageTemplate(frames=[frame], onPage=draw_page)])
    document.build(story)
    return buffer.getvalue()
