from datetime import datetime

import plotly.express as px
import streamlit as st

from tamizaje.repository import (
    CLOSED_STATUS,
    area_results_frame,
    cases_frame,
    last_import,
    operational_counts,
)
from tamizaje.ui import DISCLAIMER, page_header, require_context

page_header("Inicio", "Qué requiere atención hoy y cuál es el siguiente paso.")

engine, connection = require_context()
today = datetime.now(engine.report_timezone).date()
latest = last_import(connection)
results = area_results_frame(connection, engine)
cases = cases_frame(connection, engine)
counts = operational_counts(connection, engine, today)
connection.close()

if latest is None or results.empty:
    st.info(
        "Aún no hay envíos procesados. Importa una exportación desde Administración."
    )
    st.stop()

imported_at = datetime.fromisoformat(latest["imported_at"]).astimezone(
    engine.report_timezone
)
st.caption(
    f"{today:%d/%m/%Y} · última importación {imported_at:%d/%m/%Y %H:%M} · "
    f"scoring v{latest['scoring_version']}"
)

metrics = st.columns(4)
metrics[0].metric(
    "Casos prioritarios",
    counts["priority_cases"],
    help=f"Casos abiertos con nivel {engine.alerts.levels[0]}.",
)
metrics[1].metric(
    "Solicitudes de contacto",
    counts["contact_requests"],
    help="Alumnos que pidieron que Orientación los contacte.",
)
metrics[2].metric(
    "Seguimientos pendientes",
    counts["pending_followups"],
    help="Casos abiertos con seguimiento programado para hoy o antes.",
)
metrics[3].metric("Alumnos procesados", counts["students"])

st.subheader("Siguientes casos por atender")
open_cases = cases[cases["case_status"] != CLOSED_STATUS]
if open_cases.empty:
    st.success("No hay casos abiertos. No hay acciones pendientes.")
else:
    upcoming = open_cases.head(5)
    st.dataframe(
        upcoming.assign(
            requested=upcoming["requested_contact"].map({True: "Sí", False: "No"}),
        ).rename(
            columns={
                "priority": "Prioridad",
                "student_name": "Alumno",
                "group_name": "Grupo",
                "case_level": "Nivel",
                "requested": "Pidió contacto",
                "case_status": "Estado",
                "next_follow_up_at": "Próximo seguimiento",
            }
        )[
            [
                "Prioridad",
                "Alumno",
                "Grupo",
                "Nivel",
                "Pidió contacto",
                "Estado",
                "Próximo seguimiento",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(f"{len(open_cases)} casos abiertos en total.")

links = st.columns(2)
links[0].page_link(
    "pages/2_Casos.py", label="Revisar todos los casos", icon=":material/assignment:"
)
links[1].page_link(
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
        st.plotly_chart(figure, width="stretch")
with right:
    st.subheader("Áreas con mayor necesidad de apoyo")
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
    st.plotly_chart(figure, width="stretch")
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
        st.dataframe(lowest, hide_index=True, width="stretch")
    hidden = int((group_sizes < engine.minimum_group_size).sum())
    if hidden:
        st.caption(
            f"{hidden} grupo(s) con menos de {engine.minimum_group_size} alumnos "
            "se omiten para proteger la confidencialidad."
        )

st.caption(DISCLAIMER)
