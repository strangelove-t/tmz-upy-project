import plotly.express as px
import streamlit as st

from tamizaje.repository import CLOSED_STATUS, area_results_frame, cases_frame
from tamizaje.ui import (
    DISCLAIMER,
    LIGHT_COLORS,
    LIGHT_ORDER,
    NO_SUBMISSIONS,
    page_header,
    require_context,
    show_chart,
)

page_header("Grupos", "Resultados por carrera y grupo.")

engine, connection = require_context()
results = area_results_frame(connection, engine)
cases = cases_frame(connection, engine)
connection.close()
if results.empty:
    st.info(NO_SUBMISSIONS)
    st.stop()

columns = st.columns(2)
career = columns[0].selectbox("Carrera", sorted(results["career"].unique()))
group = columns[1].selectbox(
    "Grupo", sorted(results.loc[results["career"] == career, "group_name"].unique())
)
group_results = results[
    (results["career"] == career) & (results["group_name"] == group)
]
group_cases = cases[(cases["career"] == career) & (cases["group_name"] == group)]
size = group_results["submission_id"].nunique()
protected = size < engine.minimum_group_size

coverage = st.columns(3)
coverage[0].metric("Alumnos evaluados", size)
coverage[1].metric(
    "Casos abiertos",
    "—" if protected else int((group_cases["case_status"] != CLOSED_STATUS).sum()),
)
coverage[2].metric(
    "Resultados completos",
    "—"
    if protected
    else f"{group_results['is_complete'].mean() * 100:.0f} %",
    help="Porcentaje de resultados de área completos en el grupo.",
)

if protected:
    st.warning(
        f"Este grupo tiene menos de {engine.minimum_group_size} alumnos evaluados. "
        "Para proteger su confidencialidad no se muestran promedios, semáforos ni "
        "la lista del grupo. Consulta a cada alumno en Estudiantes."
    )
    st.caption(DISCLAIMER)
    st.stop()

left, right = st.columns(2)
with left:
    st.subheader("Promedio por área")
    averages = (
        group_results.groupby("area_name", sort=False)["normalized_score"]
        .mean()
        .round(1)
        .rename_axis("Área")
        .reset_index(name="Promedio")
    )
    figure = px.bar(
        averages,
        x="Promedio",
        y="Área",
        orientation="h",
        range_x=[0, 100],
        text="Promedio",
        labels={"Promedio": "Promedio (0–100)", "Área": ""},
    )
    figure.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
    figure.update_yaxes(autorange="reversed")
    show_chart(figure)
with right:
    st.subheader("Semáforos por área")
    distribution = (
        group_results.groupby(["area_name", "traffic_light"], sort=False)
        .size()
        .reset_index(name="Alumnos")
    )
    figure = px.bar(
        distribution,
        x="Alumnos",
        y="area_name",
        color="traffic_light",
        orientation="h",
        range_x=[0, size],
        color_discrete_map=LIGHT_COLORS,
        category_orders={"traffic_light": LIGHT_ORDER},
        labels={"area_name": "", "traffic_light": "Semáforo"},
    )
    figure.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
    figure.update_yaxes(autorange="reversed")
    show_chart(figure)

st.subheader("Casos por nivel")
by_level = (
    group_cases.groupby("case_level").size().reindex(engine.alerts.levels, fill_value=0)
)
level_columns = st.columns(len(by_level))
for column, (level, count) in zip(level_columns, by_level.items(), strict=True):
    column.metric(level, int(count))

st.subheader("Estudiantes priorizados")
students = (
    group_results.pivot_table(
        index=["submission_id", "student_name"],
        columns="area_name",
        values="normalized_score",
        sort=False,
    )
    .round(1)
    .reset_index()
)
students = students.merge(
    group_cases[["submission_id", "priority", "case_level", "case_status"]],
    on="submission_id",
    how="left",
).sort_values(["priority", "student_name"], na_position="last")
st.dataframe(
    students.drop(columns="submission_id").rename(
        columns={
            "student_name": "Alumno",
            "priority": "Prioridad",
            "case_level": "Nivel",
            "case_status": "Estado",
        }
    ),
    hide_index=True,
    width="stretch",
)
st.caption(
    "Puntajes 0–100; 100 = mayor fortaleza. Sin caso = sin alertas. " + DISCLAIMER
)
