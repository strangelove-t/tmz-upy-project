from html import escape
from io import BytesIO

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

from tamizaje.normalization import normalize_text
from tamizaje.repository import sensitive_notices_frame
from tamizaje.sensitive_summary import build_sensitive_summary
from tamizaje.ui import (
    DISCLAIMER,
    page_header,
    require_context,
    sensitive_config,
    show_sensitive_summary,
    yes_no,
)

page_header(
    "Condiciones declaradas",
    "Alumnos que declararon una neurodivergencia, una condición emocional, de "
    "personalidad o de salud física. Es información confidencial.",
)

# Igual que en Casos: los filtros se conservan al cambiar de página.
FILTER_DEFAULTS = {
    "conditions_search": "",
    "conditions_categories": [],
    "conditions_careers": [],
    "conditions_groups": [],
    "conditions_support": "Todos",
}
for key, default in FILTER_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get(f"saved_{key}", default)

engine, connection = require_context()
config = sensitive_config()
if config is None:
    st.error("No fue posible cargar la configuración de información sensible.")
    connection.close()
    st.stop()

notices = sensitive_notices_frame(connection, config)
labels = {category.code: category.label for category in config.categories}

st.info(
    "Lo declaró el propio alumno. No cambia la prioridad de los casos ni es "
    "una valoración de la universidad."
)
metrics = st.columns(len(labels))
for column, (code, label) in zip(metrics, labels.items(), strict=True):
    column.metric(
        label,
        int(notices["category_codes"].apply(lambda codes, c=code: c in codes).sum())
        if not notices.empty
        else 0,
    )

if notices.empty:
    st.success("Ningún alumno ha declarado condiciones o diagnósticos.")
    connection.close()
    st.caption(DISCLAIMER)
    st.stop()


def options(column: str) -> list[str]:
    return sorted(value for value in notices[column].dropna().unique() if value)


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


def table_controls(frame, state_key: str, title: str, file_stem: str):
    page_size = 30
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


with st.container(border=True):
    columns = st.columns([2, 1])
    categories = columns[0].multiselect(
        "Condición",
        list(labels),
        format_func=labels.get,
        key="conditions_categories",
        placeholder="Todas las condiciones",
    )
    support = columns[1].radio(
        "Solicita apoyo",
        ["Todos", "Sí", "No"],
        horizontal=True,
        key="conditions_support",
    )
    columns = st.columns(3)
    search = normalize_text(
        columns[0].text_input(
            "Buscar por nombre",
            key="conditions_search",
            placeholder="Parte del nombre",
        )
    ).casefold()
    careers = columns[1].multiselect(
        "Carrera",
        options("career"),
        key="conditions_careers",
        placeholder="Todas",
    )
    groups = columns[2].multiselect(
        "Grupo",
        options("group_name"),
        key="conditions_groups",
        placeholder="Todos",
    )

for key in FILTER_DEFAULTS:
    st.session_state[f"saved_{key}"] = st.session_state[key]

visible = notices
if categories:
    visible = visible[
        visible["category_codes"].apply(
            lambda codes: bool(set(codes) & set(categories))
        )
    ]
if support != "Todos":
    visible = visible[visible["requested_support"] == (support == "Sí")]
if careers:
    visible = visible[visible["career"].isin(careers)]
if groups:
    visible = visible[visible["group_name"].isin(groups)]
if search:
    visible = visible[
        visible["student_name"].str.casefold().str.contains(search, regex=False)
    ]
visible = visible.reset_index(drop=True)

if visible.empty:
    st.info("Sin resultados para estos filtros. Quita alguno para ampliar la lista.")
    connection.close()
    st.stop()

st.caption(
    f"{len(visible)} de {len(notices)} alumnos · Haz clic en una fila para ver "
    "lo que declaró."
)
display_notices = (
    visible.assign(
        requested_support=visible["requested_support"].map(yes_no),
        requires_review=visible["requires_review"].map(yes_no),
        has_case=visible["case_id"].notna().map(yes_no),
    )
    .rename(
        columns={
            "student_name": "Alumno",
            "group_name": "Grupo",
            "category_labels": "Condiciones",
            "requested_support": "Solicita apoyo",
            "requires_review": "Revisar respuestas",
            "has_case": "Tiene caso",
        }
    )[
        [
            "Alumno",
            "Grupo",
            "Condiciones",
            "Solicita apoyo",
            "Revisar respuestas",
            "Tiene caso",
        ]
    ]
    .reset_index(drop=True)
)
page_notices = table_controls(
    display_notices,
    "conditions",
    "Condiciones declaradas",
    "condiciones-declaradas",
)
current_page = st.session_state["conditions_page"]
selection = st.dataframe(
    styled_table(page_notices),
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-cell",
    key="conditions_table",
)

# El detalle (diagnósticos declarados) sólo se muestra al elegir a un alumno.
page_submission_ids = visible.iloc[
    current_page * 30 : current_page * 30 + len(page_notices)
]["submission_id"].tolist()
same_table_page = (
    st.session_state.get("conditions_last_display_page") == current_page
    and st.session_state.get("conditions_last_display_ids") == page_submission_ids
)
selected_rows = [
    row for row, _column in selection.selection.cells if row < len(page_notices)
] if same_table_page else []
st.session_state["conditions_last_display_page"] = current_page
st.session_state["conditions_last_display_ids"] = page_submission_ids
if selected_rows:
    notice = visible.iloc[
        current_page * 30 + selected_rows[0]
    ]
    with st.container(border=True):
        st.subheader(notice["student_name"])
        st.caption(f"{notice['career']} · Grupo {notice['group_name']}")
        show_sensitive_summary(
            build_sensitive_summary(connection, int(notice["submission_id"]), config)
        )
        if notice["case_id"] is not None:
            st.page_link(
                "pages/2_Casos.py",
                label="Este alumno también tiene un caso en Casos",
                icon=":material/assignment:",
            )

connection.close()
st.caption(DISCLAIMER)
