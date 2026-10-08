import plotly.express as px
import streamlit as st

from tamizaje.repository import area_results_frame, cases_frame, last_import
from tamizaje.ui import DISCLAIMER, LIGHT_COLORS, LIGHT_ORDER, require_context

st.title("Inicio")
st.caption(DISCLAIMER)

engine, connection = require_context()
latest = last_import(connection)
results = area_results_frame(connection, engine)
cases = cases_frame(connection, engine)
connection.close()

if latest is None or results.empty:
    st.info("Aún no hay envíos procesados.")
    st.stop()

st.caption(
    f"Última importación: {latest['imported_at'][:16].replace('T', ' ')} UTC · "
    f"cuestionario v{latest['questionnaire_version']} · "
    f"scoring v{latest['scoring_version']}"
)

open_cases = cases[cases["case_status"] != "Cerrado"]
metrics = st.columns(5)
metrics[0].metric("Alumnos procesados", results["submission_id"].nunique())
metrics[1].metric("Casos nuevos", int((cases["case_status"] == "Nuevo").sum()))
metrics[2].metric("Casos pendientes", len(open_cases))
metrics[3].metric("Solicitudes de contacto", int(cases["requested_contact"].sum()))
metrics[4].metric("Áreas incompletas", int((results["is_complete"] == 0).sum()))

left, right = st.columns(2)
with left:
    st.subheader("Casos abiertos por nivel")
    if open_cases.empty:
        st.write("No hay casos abiertos.")
    else:
        by_level = (
            open_cases.groupby("case_level")
            .size()
            .reindex(engine.alerts.levels, fill_value=0)
            .rename_axis("Nivel")
            .reset_index(name="Casos")
        )
        st.plotly_chart(
            px.bar(by_level, x="Nivel", y="Casos", text="Casos"),
            width="stretch",
        )
with right:
    st.subheader("Promedio por área")
    averages = (
        results.groupby("area_name", sort=False)["normalized_score"]
        .mean()
        .round(1)
        .rename_axis("Área")
        .reset_index(name="Promedio")
    )
    st.plotly_chart(
        px.bar(averages, x="Promedio", y="Área", orientation="h", range_x=[0, 100]),
        width="stretch",
    )

st.subheader("Distribución de semáforos por área")
distribution = (
    results.groupby(["area_name", "traffic_light"], sort=False)
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

st.subheader("Área con menor promedio por grupo")
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
        f"No hay grupos con al menos {engine.minimum_group_size} alumnos para "
        "mostrar agregados."
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
    st.dataframe(lowest, hide_index=True, width="stretch")
hidden = int((group_sizes < engine.minimum_group_size).sum())
if hidden:
    st.caption(
        f"{hidden} grupo(s) con menos de {engine.minimum_group_size} alumnos se "
        "omiten para proteger la confidencialidad."
    )
