from datetime import datetime
from html import escape
from io import BytesIO

import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

from tamizaje.repository import (
    CLOSED_STATUS,
    area_results_frame,
    cases_frame,
    last_import,
    operational_counts,
    sensitive_notices_frame,
)
from tamizaje.ui import (
    DISCLAIMER,
    NO_SUBMISSIONS,
    format_date,
    page_header,
    require_context,
    sensitive_config,
    show_chart,
)


def excel_bytes(frame) -> bytes:
    output = BytesIO()
    frame.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def pdf_bytes(frame, title: str) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=18,
        rightMargin=18,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontName = "Helvetica"
    cell_style.fontSize = 7
    cell_style.leading = 9
    header_style = cell_style.clone("TableHeader")
    header_style.textColor = colors.white
    rows = [
        [
            Paragraph(f"<b>{escape(str(column))}</b>", header_style)
            for column in frame
        ]
    ]
    rows.extend(
        [Paragraph(escape(str(value)), cell_style) for value in row]
        for row in frame.itertuples(index=False, name=None)
    )
    table = LongTable(
        rows,
        colWidths=[
            (landscape(letter)[0] - 36) / len(frame.columns)
        ]
        * len(frame.columns),
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A0870")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.HexColor("#F6F8FA"),
                        colors.HexColor("#EEE7F2"),
                    ],
                ),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#FFFFFF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    document.build([Paragraph(escape(title), styles["Title"]), table])
    return output.getvalue()


def table_controls(
    frame, state_key: str, title: str, file_stem: str, page_size: int = 30
):
    page_count = max(1, (len(frame) + page_size - 1) // page_size)
    page_key = f"{state_key}_page"
    current_page = max(
        0, min(int(st.session_state.get(page_key, 0)), page_count - 1)
    )
    st.session_state[page_key] = current_page
    previous_column, page_column, next_column, excel_column, pdf_column = st.columns(
        [1, 2, 1, 1, 1]
    )
    if previous_column.button(
        "← Anterior",
        disabled=current_page == 0,
        key=f"{state_key}_previous_page",
    ):
        st.session_state[page_key] = current_page - 1
        st.rerun()
    page_column.markdown(
        f"<div style='text-align:center; padding-top:0.4rem'>"
        f"Página {current_page + 1} de {page_count}</div>",
        unsafe_allow_html=True,
    )
    if next_column.button(
        "Siguiente →",
        disabled=current_page == page_count - 1,
        key=f"{state_key}_next_page",
    ):
        st.session_state[page_key] = current_page + 1
        st.rerun()
    excel_column.download_button(
        "Excel",
        data=excel_bytes(frame),
        file_name=f"{file_stem}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{state_key}_download_excel",
        width="stretch",
    )
    pdf_column.download_button(
        "PDF",
        data=pdf_bytes(frame, title),
        file_name=f"{file_stem}.pdf",
        mime="application/pdf",
        key=f"{state_key}_download_pdf",
        width="stretch",
    )
    start = current_page * page_size
    return frame.iloc[start : start + page_size].reset_index(drop=True)


def styled_table(frame):
    return frame.style.apply(
        lambda row: [
            "background-color: #F6F8FA"
            if row.name % 2 == 0
            else "background-color: #EEE7F2"
        ]
        * len(row),
        axis=1,
    ).set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [
                    ("background-color", "#4A0870"),
                    ("color", "#FFFFFF"),
                    ("font-weight", "bold"),
                ],
            }
        ]
    )


page_header("Inicio", "Qué requiere atención hoy y cuál es el siguiente paso.")

engine, connection = require_context()
today = datetime.now(engine.report_timezone).date()
latest = last_import(connection)
results = area_results_frame(connection, engine)
cases = cases_frame(connection, engine)
counts = operational_counts(connection, engine, today)
summary_config = sensitive_config()
notices = (
    sensitive_notices_frame(connection, summary_config)
    if summary_config is not None
    else None
)
connection.close()

if latest is None or results.empty:
    st.info(NO_SUBMISSIONS)
    st.stop()

imported_at = datetime.fromisoformat(latest["imported_at"]).astimezone(
    engine.report_timezone
)
st.caption(
    f"Hoy es {today:%d/%m/%Y} · respuestas cargadas el {imported_at:%d/%m/%Y}"
)

metrics = st.columns(5)
metrics[0].metric("Casos prioritarios", counts["priority_cases"])
metrics[0].caption(f"Abiertos con nivel {engine.alerts.levels[0]}.")
metrics[1].metric("Solicitudes de contacto", counts["contact_requests"])
metrics[1].caption("Alumnos que pidieron que Orientación los contacte.")
metrics[2].metric("Seguimientos", counts["pending_followups"])
metrics[2].caption("Pendientes con fecha de hoy o anterior.")
metrics[3].metric("Alumnos procesados", counts["students"])
metrics[3].caption("Respondieron el cuestionario.")
metrics[4].metric(
    "Información declarada por revisar", len(notices) if notices is not None else "—"
)
metrics[4].caption("Avisos informativos; no modifican la prioridad.")

st.subheader("Siguientes casos por atender")
open_cases = cases[cases["case_status"] != CLOSED_STATUS]
if open_cases.empty:
    st.success("No hay casos abiertos. No hay acciones pendientes.")
else:
    upcoming = open_cases
    display_upcoming = (
        upcoming.assign(
            requested=upcoming["requested_contact"].map({True: "Sí", False: "No"}),
            next_follow_up_at=upcoming["next_follow_up_at"].map(format_date),
        ).rename(
            columns={
                "priority": "#",
                "student_name": "Alumno",
                "group_name": "Grupo",
                "case_level": "Nivel",
                "requested": "Pidió contacto",
                "case_status": "Estado",
                "next_follow_up_at": "Seguimiento",
            }
        )[
            [
                "#",
                "Alumno",
                "Grupo",
                "Nivel",
                "Pidió contacto",
                "Estado",
                "Seguimiento",
            ]
        ]
        .reset_index(drop=True)
    )
    page_upcoming = table_controls(
        display_upcoming,
        "home_cases",
        "Siguientes casos por atender",
        "siguientes-casos",
        page_size=5,
    )
    st.dataframe(
        styled_table(page_upcoming),
        hide_index=True,
        width="stretch",
        column_config={"#": st.column_config.NumberColumn(width=45)},
    )
    st.caption(f"{len(open_cases)} casos abiertos en total.")

links = st.columns(3)
links[0].page_link(
    "pages/2_Casos.py", label="Revisar todos los casos", icon=":material/assignment:"
)
links[1].page_link(
    "pages/7_Condiciones.py",
    label="Ver condiciones declaradas",
    icon=":material/health_and_safety:",
)
links[2].page_link(
    "pages/4_Estudiantes.py", label="Buscar un estudiante", icon=":material/search:"
)

left, right = st.columns(2)
with left:
    st.subheader("Casos abiertos por nivel")
    if open_cases.empty:
        st.write("Sin casos abiertos.")
    else:
        by_level = (
            open_cases.groupby("case_level")
            .size()
            .reindex(engine.alerts.levels, fill_value=0)
            .rename_axis("Nivel")
            .reset_index(name="Casos")
        )
        figure = px.bar(by_level, x="Casos", y="Nivel", orientation="h", text="Casos")
        figure.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
        figure.update_yaxes(
            categoryorder="array", categoryarray=by_level["Nivel"][::-1]
        )
        show_chart(figure)
with right:
    st.subheader("Áreas con más necesidad")
    averages = (
        results.groupby("area_name", sort=False)["normalized_score"]
        .mean()
        .round(1)
        .sort_values()
        .rename_axis("Área")
        .reset_index(name="Promedio")
    )
    figure = px.bar(
        averages.head(5),
        x="Promedio",
        y="Área",
        orientation="h",
        range_x=[0, 100],
        text="Promedio",
    )
    figure.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
    figure.update_yaxes(autorange="reversed")
    show_chart(figure)
    st.caption("Promedio institucional 0–100; 100 = mayor fortaleza.")

with st.expander("Área con menor promedio por grupo"):
    group_sizes = results.groupby(["career", "group_name"])["submission_id"].nunique()
    eligible = group_sizes[group_sizes >= engine.minimum_group_size].index
    group_means = (
        results.set_index(["career", "group_name"])
        .loc[lambda frame: frame.index.isin(eligible)]
        .reset_index()
        .groupby(["career", "group_name", "area_name"])["normalized_score"]
        .mean()
        .reset_index()
    )
    if group_means.empty:
        st.write(
            f"Ningún grupo alcanza {engine.minimum_group_size} alumnos; los "
            "promedios por grupo se ocultan para proteger la confidencialidad."
        )
    else:
        lowest = group_means.loc[
            group_means.groupby(["career", "group_name"])["normalized_score"].idxmin()
        ].rename(
            columns={
                "career": "Carrera",
                "group_name": "Grupo",
                "area_name": "Área más baja",
                "normalized_score": "Promedio",
            }
        )
        lowest["Promedio"] = lowest["Promedio"].round(1)
        lowest = lowest.reset_index(drop=True)
        page_lowest = table_controls(
            lowest,
            "home_lowest_areas",
            "Área con menor promedio por grupo",
            "areas-por-grupo",
        )
        st.dataframe(styled_table(page_lowest), hide_index=True, width="stretch")
    hidden = int((group_sizes < engine.minimum_group_size).sum())
    if hidden:
        st.caption(
            f"{hidden} grupo(s) con menos de {engine.minimum_group_size} alumnos "
            "se omiten para proteger la confidencialidad."
        )

st.caption(DISCLAIMER)
