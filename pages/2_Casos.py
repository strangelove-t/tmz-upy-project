from datetime import date
from html import escape
from io import BytesIO

import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

from tamizaje.cases import CASE_STATUSES, CONTACT_STATUSES
from tamizaje.database import add_case_note, update_case
from tamizaje.normalization import normalize_text
from tamizaje.repository import (
    CLOSED_STATUS,
    area_results_frame,
    case_notes,
    cases_frame,
    sensitive_notices_frame,
    submission_alerts,
    submission_responses,
)
from tamizaje.sensitive_summary import build_sensitive_summary
from tamizaje.ui import (
    DISCLAIMER,
    LIGHT_COLORS,
    LIGHT_ORDER,
    area_names,
    format_date,
    page_header,
    question_texts,
    require_context,
    sensitive_config,
    show_chart,
    show_sensitive_summary,
    status_row,
    yes_no,
)

page_header(
    "Casos",
    "Primero aparecen quienes pidieron contacto y los casos más urgentes.",
)

# Los filtros conservan su valor al cambiar de página durante la sesión.
OPEN_STATUSES = [status for status in CASE_STATUSES if status != CLOSED_STATUS]
FILTER_DEFAULTS = {
    "cases_search": "",
    "cases_careers": [],
    "cases_groups": [],
    "cases_levels": [],
    "cases_categories": [],
    "cases_statuses": OPEN_STATUSES,
    "cases_assignees": [],
}
# Streamlit borra el estado de un widget al salir de su página; por eso el
# valor se respalda en una clave propia y se restaura al volver.
for key, default in FILTER_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get(f"saved_{key}", default)

engine, connection = require_context()
cases = cases_frame(connection, engine)
summary_config = sensitive_config()
notices = (
    sensitive_notices_frame(connection, summary_config)
    if summary_config is not None
    else None
)
if cases.empty:
    st.info("No hay casos registrados. Los casos se crean al importar respuestas.")
    if notices is not None and not notices.empty:
        st.page_link(
            "pages/7_Condiciones.py",
            label=f"{len(notices)} alumnos declararon condiciones: ver y filtrar",
            icon=":material/health_and_safety:",
        )
    connection.close()
    st.stop()


def options(column: str) -> list[str]:
    return sorted(value for value in cases[column].dropna().unique() if value)


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
        [
            Paragraph(escape(str(value)), cell_style)
            for value in row
        ]
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
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.HexColor("#F6F8FA"),
                    colors.HexColor("#EEE7F2"),
                ]),
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


search = normalize_text(
    st.text_input(
        "Buscar por nombre o correo",
        key="cases_search",
        placeholder="Escribe al menos una parte del nombre o correo",
    )
).casefold()
with st.expander("Filtrar casos", expanded=False):
    columns = st.columns(3)
    careers = columns[0].multiselect("Carrera", options("career"), key="cases_careers")
    groups = columns[1].multiselect("Grupo", options("group_name"), key="cases_groups")
    levels = columns[2].multiselect(
        "Nivel", list(engine.alerts.levels), key="cases_levels"
    )
    columns = st.columns(3)
    categories = columns[0].multiselect(
        "Categoría",
        sorted({rule.alert_category for rule in engine.alerts.rules}),
        key="cases_categories",
    )
    statuses = columns[1].multiselect(
        "Estado", list(CASE_STATUSES), key="cases_statuses"
    )
    assignees = columns[2].multiselect(
        "Responsable", options("assigned_to"), key="cases_assignees"
    )

for key in FILTER_DEFAULTS:
    st.session_state[f"saved_{key}"] = st.session_state[key]

visible = cases
if careers:
    visible = visible[visible["career"].isin(careers)]
if groups:
    visible = visible[visible["group_name"].isin(groups)]
if levels:
    visible = visible[visible["case_level"].isin(levels)]
if categories:
    visible = visible[
        visible["categories"].apply(
            lambda value: bool(set(value.split(",")) & set(categories))
        )
    ]
if statuses:
    visible = visible[visible["case_status"].isin(statuses)]
if assignees:
    visible = visible[visible["assigned_to"].isin(assignees)]
if search:
    visible = visible[
        visible["student_name"].str.casefold().str.contains(search, regex=False)
        | visible["student_upn"].str.casefold().str.contains(search, regex=False)
    ]

if visible.empty:
    st.info(
        "Sin resultados para estos filtros. Cambia la búsqueda o abre "
        "«Filtrar casos» para ampliar los criterios."
    )
    connection.close()
    st.stop()

page_count = (len(visible) + 29) // 30
current_page = min(st.session_state.get("cases_page", 0), page_count - 1)
st.session_state["cases_page"] = current_page
previous_column, page_column, next_column, excel_column, pdf_column = st.columns(
    [1, 2, 1, 1, 1]
)
if previous_column.button(
    "← Anterior", disabled=current_page == 0, key="cases_previous_page"
):
    st.session_state["cases_page"] = current_page - 1
    st.rerun()
page_column.markdown(
    f"<div style='text-align:center; padding-top:0.4rem'>"
    f"Página {current_page + 1} de {page_count}</div>",
    unsafe_allow_html=True,
)
if next_column.button(
    "Siguiente →", disabled=current_page == page_count - 1, key="cases_next_page"
):
    st.session_state["cases_page"] = current_page + 1
    st.rerun()

export_cases = (
    visible.assign(
        requested_contact=visible["requested_contact"].map(yes_no),
        next_follow_up_at=visible["next_follow_up_at"].map(format_date),
        assigned_to=visible["assigned_to"].fillna("—"),
        sensitive_information=visible["submission_id"]
        .map(
            dict(zip(notices["submission_id"], notices["category_labels"]))
            if notices is not None
            else {}
        )
        .fillna("No"),
    )
    .rename(
        columns={
            "priority": "#",
            "student_name": "Alumno",
            "group_name": "Grupo",
            "case_level": "Nivel",
            "requested_contact": "Pidió contacto",
            "case_status": "Estado",
            "next_follow_up_at": "Seguimiento",
            "sensitive_information": "Condición declarada",
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
            "Condición declarada",
        ]
    ]
    .reset_index(drop=True)
)
excel_column.download_button(
    "Excel",
    data=excel_bytes(export_cases),
    file_name="casos.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="cases_download_excel",
    width="stretch",
)
pdf_column.download_button(
    "PDF",
    data=pdf_bytes(export_cases, "Casos"),
    file_name="casos.pdf",
    mime="application/pdf",
    key="cases_download_pdf",
    width="stretch",
)

start = current_page * 30
page_cases = visible.iloc[start : start + 30]
st.caption(f"{len(visible)} de {len(cases)} casos")
st.caption("Haz clic en una fila para abrir el caso.")
display_cases = (
    page_cases.assign(
        requested_contact=page_cases["requested_contact"].map(yes_no),
        next_follow_up_at=page_cases["next_follow_up_at"].map(format_date),
        assigned_to=page_cases["assigned_to"].fillna("—"),
        sensitive_information=page_cases["submission_id"]
        .map(
            dict(zip(notices["submission_id"], notices["category_labels"]))
            if notices is not None
            else {}
        )
        .fillna("No"),
    ).rename(
        columns={
            "priority": "#",
            "student_name": "Alumno",
            "group_name": "Grupo",
            "case_level": "Nivel",
            "requested_contact": "Pidió contacto",
            "case_status": "Estado",
            "next_follow_up_at": "Seguimiento",
            "sensitive_information": "Condición declarada",
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
            "Condición declarada",
        ]
    ]
    .reset_index(drop=True)
)
styled_cases = (
    display_cases.style.apply(
        lambda row: [
            "background-color: #F6F8FA"
            if row.name % 2 == 0
            else "background-color: #EEE7F2"
        ]
        * len(row),
        axis=1,
    )
    .set_table_styles(
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
)
selection = st.dataframe(
    styled_cases,
    hide_index=True,
    width="stretch",
    on_select="rerun",
    # Un clic en cualquier celda abre el caso de esa fila.
    selection_mode="single-cell",
    key="cases_table",
    column_config={"#": st.column_config.NumberColumn(width=45)},
)

# Sin selección (o si los filtros cambiaron la tabla) se abre el primer caso.
selected_rows = [
    row for row, _column in selection.selection.cells if row < len(page_cases)
]
page_case_ids = page_cases["case_id"].tolist()
same_table_page = (
    st.session_state.get("cases_last_display_page") == current_page
    and st.session_state.get("cases_last_display_ids") == page_case_ids
)
if selected_rows and same_table_page:
    st.session_state["cases_selected_case_id"] = int(
        page_cases.iloc[selected_rows[0]]["case_id"]
    )

selected_case_id = st.session_state.get("cases_selected_case_id")
selected_case = visible[visible["case_id"] == selected_case_id]
if selected_case.empty:
    case = page_cases.iloc[0]
    st.session_state["cases_selected_case_id"] = int(case["case_id"])
else:
    case = selected_case.iloc[0]
st.session_state["cases_last_display_page"] = current_page
st.session_state["cases_last_display_ids"] = page_case_ids
case_id = int(case["case_id"])
st.subheader(f"#{case['priority']} · {case['student_name']}")
submission_id = int(case["submission_id"])
alerts = submission_alerts(connection, submission_id, engine.alerts.version)
area_results = area_results_frame(connection, engine)
area_results = area_results[area_results["submission_id"] == submission_id]
responses = submission_responses(connection, submission_id, question_texts())
responses_by_question = dict(
    zip(responses["question_code"], responses["response_raw"], strict=True)
)


def forms_response_text(question_code: str) -> str:
    response = responses_by_question.get(question_code)
    if not isinstance(response, str):
        return "Sin respuesta registrada"
    return normalize_text(response) or "Sin respuesta registrada"


critical_area = area_names(engine).get(case["critical_area_code"], "—")

with st.container(border=True):
    status_row(
        {
            "Nivel": case["case_level"],
            "Estado": case["case_status"],
            "Contacto": case["contact_status"],
            "Responsable": case["assigned_to"] or "Sin asignar",
            "Área más baja": critical_area,
        }
    )

reason_tab, results_tab, follow_up_tab, conditions_tab, notes_tab = st.tabs(
    [
        "Motivo y alertas",
        "Resultados área",
        "Seguimiento",
        "Condiciones y apoyos",
        "Notas",
    ]
)

with reason_tab:
    st.markdown(f"**Por qué aparece en esta posición:** {case['priority_reason']}")
    st.markdown(f"**Fuente:** {case['case_source']}")
    if (alerts["alert_level"] == "Revisión manual").any():
        st.warning(
            "Incluye texto abierto que debe leerse completo antes de "
            "clasificarlo. Ábrelo en Estudiantes › Respuestas."
        )
    st.markdown(f"**Alertas ({len(alerts)})**")
    alert_types = alerts["alert_level"].dropna().unique().tolist()
    preferred_types = [
        "Atención prioritaria",
        "Seguimiento preventivo",
        "Revisión manual",
    ]
    ordered_types = [level for level in preferred_types if level in alert_types]
    ordered_types.extend(sorted(set(alert_types) - set(ordered_types)))
    type_colors = {
        "Atención prioritaria": ("#5B0A8A", "#F4EDF8"),
        "Seguimiento preventivo": ("#FDA20C", "#FFF4DD"),
        "Revisión manual": ("#7D42A0", "#F0E7F5"),
    }
    fallback_colors = [
        ("#5B0A8A", "#F4EDF8"),
        ("#FDA20C", "#FFF4DD"),
        ("#7D42A0", "#F0E7F5"),
    ]
    for index, alert_type in enumerate(ordered_types):
        group = alerts[alerts["alert_level"] == alert_type]
        accent, tint = type_colors.get(
            alert_type, fallback_colors[index % len(fallback_colors)]
        )
        with st.container(border=True):
            st.markdown(
                f"<div style='background:{tint}; border-left:6px solid {accent}; "
                "border-radius:8px; padding:0.55rem 0.75rem; font-weight:600'>"
                f"{escape(alert_type)}</div>",
                unsafe_allow_html=True,
            )
            with st.expander(
                f"{alert_type} · {format_date(case['detected_at'])} "
                f"· {len(group)} alertas"
            ):
                for alert in group.itertuples():
                    with st.container(border=True):
                        st.markdown(f"**{alert.alert_category}**")
                        st.write(alert.alert_reason)
                        if alert.alert_level == "Revisión manual":
                            st.markdown("**Respuesta del formulario (Forms):**")
                            st.write(forms_response_text(alert.question_code))
                        else:
                            st.caption(f"Acción sugerida: {alert.suggested_action}")

with results_tab:
    if area_results.empty:
        st.info("Aún no hay resultados para esta respuesta.")
    else:
        chart = area_results.assign(
            score=area_results["normalized_score"].fillna(0).round(1),
            label=area_results.apply(
                lambda row: (
                    f"{row.normalized_score:.1f} · {row.traffic_light}"
                    if row.is_complete
                    else "Incompleta"
                ),
                axis=1,
            ),
        )
        figure = px.bar(
            chart,
            x="score",
            y="area_name",
            color="traffic_light",
            orientation="h",
            range_x=[0, 100],
            text="label",
            color_discrete_map=LIGHT_COLORS,
            category_orders={"traffic_light": LIGHT_ORDER},
            labels={"score": "Puntaje (0–100)", "area_name": "", "traffic_light": ""},
        )
        figure.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
        figure.update_yaxes(autorange="reversed")
        show_chart(figure)

        strengths = area_results[area_results["traffic_light"] == "Verde"]
        opportunities = area_results[
            area_results["traffic_light"].isin(["Amarillo", "Rojo"])
        ]
        incomplete = area_results[area_results["is_complete"] == 0]
        columns = st.columns(2)
        with columns[0]:
            st.markdown("**Fortalezas**")
            st.write(", ".join(strengths["area_name"]) or "Ninguna área en verde.")
        with columns[1]:
            st.markdown("**Áreas de oportunidad**")
            st.write(
                ", ".join(
                    f"{row.area_name} ({row.traffic_light})"
                    for row in opportunities.itertuples()
                )
                or "Ninguna área en amarillo o rojo."
            )
        if not incomplete.empty:
            st.warning(
                "Áreas incompletas que requieren revisión: "
                + ", ".join(incomplete["area_name"])
            )

        st.markdown("**Recomendaciones**")
        recommendations = {
            recommendation.recommendation_code: recommendation
            for recommendation in engine.recommendations
        }
        for row in area_results.itertuples():
            recommendation = recommendations.get(row.recommendation_code)
            if recommendation is None:
                continue
            with st.expander(f"{row.area_name} · {row.traffic_light}"):
                st.markdown(
                    f"**Para el alumno:** {recommendation.student_recommendation}"
                )
                st.markdown(
                    f"**Para el personal:** {recommendation.staff_recommendation}"
                )

with follow_up_tab:
    if st.session_state.pop("cases_saved", False):
        st.success("Seguimiento actualizado.")
    stored = connection.execute(
        "SELECT referral_destination, closure_reason, resolution_notes "
        "FROM cases WHERE id = ?",
        (case_id,),
    ).fetchone()
    with st.form("case_update"):
        st.markdown("**Contacto**")
        columns = st.columns(3)
        contact = columns[0].selectbox(
            "Contacto",
            CONTACT_STATUSES,
            index=CONTACT_STATUSES.index(case["contact_status"]),
        )
        assigned = columns[1].text_input("Responsable", case["assigned_to"] or "")
        follow_up = columns[2].date_input(
            "Próximo seguimiento",
            value=(
                date.fromisoformat(case["next_follow_up_at"])
                if case["next_follow_up_at"]
                else None
            ),
            format="DD/MM/YYYY",
        )
        st.markdown("**Seguimiento**")
        columns = st.columns(2)
        status = columns[0].selectbox(
            "Estado", CASE_STATUSES, index=CASE_STATUSES.index(case["case_status"])
        )
        referral = columns[1].text_input("Canalizado a", stored[0] or "")
        st.markdown("**Cierre**")
        closure = st.text_input(
            "Motivo de cierre",
            stored[1] or "",
            help="Se registra la fecha de cierre al cambiar el estado a Cerrado.",
        )
        resolution = st.text_area("Notas de resolución", stored[2] or "")
        if st.form_submit_button("Guardar seguimiento", type="primary"):
            update_case(
                connection,
                case_id,
                case_status=status,
                contact_status=contact,
                assigned_to=normalize_text(assigned) or None,
                next_follow_up_at=follow_up.isoformat() if follow_up else None,
                referral_destination=normalize_text(referral) or None,
                closure_reason=normalize_text(closure) or None,
                resolution_notes=normalize_text(resolution) or None,
            )
            st.session_state["cases_saved"] = True
            st.rerun()

with conditions_tab:
    if summary_config is None:
        st.error("No fue posible cargar la configuración de información sensible.")
    else:
        show_sensitive_summary(
            build_sensitive_summary(connection, submission_id, summary_config)
        )

with notes_tab:
    with st.form("case_note", clear_on_submit=True):
        author = st.text_input("Autor")
        note = st.text_area("Nota")
        if st.form_submit_button("Agregar nota"):
            try:
                add_case_note(connection, case_id, author, note)
            except ValueError:
                st.error("La nota requiere autor y contenido.")
            else:
                st.success("Nota agregada.")
    notes = case_notes(connection, case_id)
    if notes.empty:
        st.caption("Aún no hay notas para este caso.")
    for note_row in notes.itertuples():
        st.markdown(
            f"**{format_date(note_row.created_at, engine.report_timezone)}**"
        )
        st.write(note_row.note)

connection.close()
st.caption(DISCLAIMER)
