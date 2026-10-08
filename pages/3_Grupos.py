import plotly.express as px
import streamlit as st

from tamizaje.repository import area_results_frame, cases_frame
from tamizaje.ui import DISCLAIMER, LIGHT_COLORS, LIGHT_ORDER, require_context

st.title("Resultados por carrera y grupo")
st.caption(DISCLAIMER)

engine, connection = require_context()
results = area_results_frame(connection, engine)
cases = cases_frame(connection, engine)
connection.close()
if results.empty:
    st.info("Aún no hay envíos procesados.")
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

st.metric("Alumnos evaluados", size)
if size < engine.minimum_group_size:
    st.warning(
        f"El grupo tiene menos de {engine.minimum_group_size} alumnos; los "
        "agregados se omiten para proteger la confidencialidad."
    )
else:
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
        st.plotly_chart(
            px.bar(averages, x="Promedio", y="Área", orientation="h", range_x=[0, 100]),
            width="stretch",
        )
    with right:
        st.subheader("Semáforos por área")
        distribution = (
            group_results.groupby(["area_name", "traffic_light"], sort=False)
            .size()
            .reset_index(name="Alumnos")
        )
        st.plotly_chart(
            px.bar(
                distribution,
                x="Alumnos",
                y="area_name",
                color="traffic_light",
                orientation="h",
                color_discrete_map=LIGHT_COLORS,
                category_orders={"traffic_light": LIGHT_ORDER},
                labels={"area_name": "Área", "traffic_light": "Semáforo"},
            ),
            width="stretch",
        )

    st.subheader("Casos por nivel")
    by_level = (
        group_cases.groupby("case_level")
        .size()
        .reindex(engine.alerts.levels, fill_value=0)
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
