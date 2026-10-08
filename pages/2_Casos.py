from datetime import date

import streamlit as st

from tamizaje.cases import CASE_STATUSES, CONTACT_STATUSES
from tamizaje.database import add_case_note, update_case
from tamizaje.normalization import normalize_text
from tamizaje.repository import case_notes, cases_frame, submission_alerts
from tamizaje.ui import DISCLAIMER, area_names, require_context

st.set_page_config(page_title="Casos · Tamizaje UPY", page_icon="📋", layout="wide")
st.title("Casos")
st.caption(
    "Orden predeterminado: solicitud de contacto, nivel, menor área, alertas "
    "prioritarias, total de alertas y antigüedad. " + DISCLAIMER
)

engine, connection = require_context()
cases = cases_frame(connection, engine)
if cases.empty:
    st.info("No hay casos registrados.")
    connection.close()
    st.stop()


def options(column: str) -> list[str]:
    return sorted(value for value in cases[column].dropna().unique() if value)


filters = st.columns(3)
careers = filters[0].multiselect("Carrera", options("career"))
groups = filters[1].multiselect("Grupo", options("group_name"))
levels = filters[2].multiselect("Nivel", list(engine.alerts.levels))
filters = st.columns(3)
categories = filters[0].multiselect(
    "Categoría",
    sorted({rule.alert_category for rule in engine.alerts.rules}),
)
statuses = filters[1].multiselect(
    "Estado", list(CASE_STATUSES), default=[s for s in CASE_STATUSES if s != "Cerrado"]
)
assignees = filters[2].multiselect("Responsable", options("assigned_to"))
search = normalize_text(st.text_input("Buscar por nombre o correo")).casefold()

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

names = area_names(engine)
table = visible.assign(
    critical_area=visible["critical_area_code"].map(names),
).rename(
    columns={
        "priority": "Prioridad",
        "student_name": "Alumno",
        "career": "Carrera",
        "group_name": "Grupo",
        "case_level": "Nivel",
        "requested_contact": "Solicitó contacto",
        "lowest_area_score": "Área más baja",
        "critical_area": "Área crítica",
        "priority_alert_count": "Alertas prioritarias",
        "total_alert_count": "Alertas",
        "case_status": "Estado",
        "contact_status": "Contacto",
        "assigned_to": "Responsable",
        "priority_reason": "Por qué aparece aquí",
    }
)
st.caption(f"{len(visible)} de {len(cases)} casos")
st.dataframe(
    table[
        [
            "Prioridad",
            "Alumno",
            "Carrera",
            "Grupo",
            "Nivel",
            "Solicitó contacto",
            "Área más baja",
            "Área crítica",
            "Alertas prioritarias",
            "Alertas",
            "Estado",
            "Contacto",
            "Responsable",
            "Por qué aparece aquí",
        ]
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "Área más baja": st.column_config.NumberColumn(format="%.1f"),
    },
)

if visible.empty:
    connection.close()
    st.stop()

st.header("Seguimiento")
labels = {
    int(row.case_id): f"#{row.priority} · {row.student_name} · {row.case_level}"
    for row in visible.itertuples()
}
case_id = st.selectbox("Caso", list(labels), format_func=labels.get)
case = visible[visible["case_id"] == case_id].iloc[0]

submission_id = int(case["submission_id"])
alerts = submission_alerts(connection, submission_id, engine.alerts.version)
if (alerts["alert_level"] == "Revisión manual").any():
    st.warning(
        "Este caso incluye texto abierto que debe leerse completo antes de "
        "clasificarlo. Consulta el expediente del estudiante."
    )
st.dataframe(
    alerts.rename(
        columns={
            "alert_level": "Nivel",
            "alert_category": "Categoría",
            "alert_reason": "Motivo",
            "suggested_action": "Acción sugerida",
        }
    )[["Nivel", "Categoría", "Motivo", "Acción sugerida"]],
    hide_index=True,
    width="stretch",
)

with st.form("case_update"):
    columns = st.columns(3)
    status = columns[0].selectbox(
        "Estado", CASE_STATUSES, index=CASE_STATUSES.index(case["case_status"])
    )
    contact = columns[1].selectbox(
        "Contacto",
        CONTACT_STATUSES,
        index=CONTACT_STATUSES.index(case["contact_status"]),
    )
    assigned = columns[2].text_input("Responsable", case["assigned_to"] or "")
    columns = st.columns(2)
    follow_up = columns[0].date_input(
        "Próximo seguimiento",
        value=(
            date.fromisoformat(case["next_follow_up_at"])
            if case["next_follow_up_at"]
            else None
        ),
    )
    stored = connection.execute(
        "SELECT referral_destination, closure_reason, resolution_notes "
        "FROM cases WHERE id = ?",
        (case_id,),
    ).fetchone()
    referral = columns[1].text_input("Canalizado a", stored[0] or "")
    closure = st.text_input("Motivo de cierre", stored[1] or "")
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
        st.success("Seguimiento actualizado.")
        st.rerun()

st.subheader("Notas del caso")
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
    st.write("Sin notas.")
else:
    for note_row in notes.itertuples():
        st.markdown(f"**{note_row.author}** · {note_row.created_at[:16]}")
        st.write(note_row.note)
connection.close()
