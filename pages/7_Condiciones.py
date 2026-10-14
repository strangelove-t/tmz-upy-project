import streamlit as st

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
selection = st.dataframe(
    visible.assign(
        requested_support=visible["requested_support"].map(yes_no),
        requires_review=visible["requires_review"].map(yes_no),
        has_case=visible["case_id"].notna().map(yes_no),
    ).rename(
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
    ],
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-cell",
    key="conditions_table",
)

# El detalle (diagnósticos declarados) sólo se muestra al elegir a un alumno.
selected_rows = [
    row for row, _column in selection.selection.cells if row < len(visible)
]
if selected_rows:
    notice = visible.iloc[selected_rows[0]]
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
