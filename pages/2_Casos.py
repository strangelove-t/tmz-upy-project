from datetime import date

import streamlit as st

from tamizaje.cases import CASE_STATUSES, CONTACT_STATUSES
from tamizaje.database import add_case_note, update_case
from tamizaje.normalization import normalize_text
from tamizaje.repository import (
    CLOSED_STATUS,
    case_notes,
    cases_frame,
    submission_alerts,
)
from tamizaje.ui import (
    DISCLAIMER,
    area_names,
    format_date,
    page_header,
    require_context,
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
if cases.empty:
    st.info("No hay casos registrados. Los casos se crean al importar respuestas.")
    connection.close()
    st.stop()


def options(column: str) -> list[str]:
    return sorted(value for value in cases[column].dropna().unique() if value)


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

st.caption(f"{len(visible)} de {len(cases)} casos")
st.caption("Haz clic en una fila para abrir el caso.")
selection = st.dataframe(
    visible.assign(
        requested_contact=visible["requested_contact"].map(yes_no),
        next_follow_up_at=visible["next_follow_up_at"].map(format_date),
        assigned_to=visible["assigned_to"].fillna("—"),
    ).rename(
        columns={
            "priority": "Prioridad",
            "student_name": "Alumno",
            "group_name": "Grupo",
            "case_level": "Nivel",
            "requested_contact": "Pidió contacto",
            "case_status": "Estado",
            "next_follow_up_at": "Seguimiento",
            "assigned_to": "Responsable",
        }
    )[
        [
            "Prioridad",
            "Alumno",
            "Grupo",
            "Nivel",
            "Pidió contacto",
            "Estado",
            "Seguimiento",
            "Responsable",
        ]
    ],
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    key="cases_table",
    column_config={"Prioridad": st.column_config.NumberColumn(width="small")},
)

# Sin selección (o si los filtros cambiaron la tabla) se abre el primer caso.
selected_rows = [row for row in selection.selection.rows if row < len(visible)]
case = visible.iloc[selected_rows[0] if selected_rows else 0]
case_id = int(case["case_id"])
st.subheader(f"#{case['priority']} · {case['student_name']}")
submission_id = int(case["submission_id"])
alerts = submission_alerts(connection, submission_id, engine.alerts.version)
critical_area = area_names(engine).get(case["critical_area_code"], "—")

with st.container(border=True):
    status_row(
        {
            "Nivel": case["case_level"],
            "Estado": case["case_status"],
            "Contacto": case["contact_status"],
            "Área más baja": critical_area,
        }
    )

reason_tab, follow_up_tab, notes_tab = st.tabs(
    ["Motivo y alertas", "Seguimiento", "Notas"]
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
    for alert in alerts.itertuples():
        with st.container(border=True):
            st.markdown(f"**{alert.alert_level}** · {alert.alert_category}")
            st.write(alert.alert_reason)
            st.caption(f"Acción sugerida: {alert.suggested_action}")

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
            f"**{note_row.author}** · "
            f"{format_date(note_row.created_at, engine.report_timezone)}"
        )
        st.write(note_row.note)

connection.close()
st.caption(DISCLAIMER)
