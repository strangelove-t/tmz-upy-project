import plotly.express as px
import streamlit as st

from tamizaje.database import set_current_submission
from tamizaje.normalization import normalize_text
from tamizaje.repository import (
    area_results_frame,
    case_notes,
    students_frame,
    submission_alerts,
    submission_case,
    submission_responses,
)
from tamizaje.ui import DISCLAIMER, LIGHT_COLORS, question_texts, require_context

st.set_page_config(
    page_title="Estudiantes · Tamizaje UPY", page_icon="🧑‍🎓", layout="wide"
)
st.title("Expediente del estudiante")
RESPONSE_COLUMNS = ["question_code", "question_text", "response_raw"]
st.caption(DISCLAIMER)

engine, connection = require_context()
students = students_frame(connection)
if students.empty:
    st.info("Aún no hay envíos procesados.")
    connection.close()
    st.stop()

search = normalize_text(st.text_input("Buscar por nombre o correo")).casefold()
current = students[students["is_current"] == 1]
if search:
    current = current[
        current["student_name"].str.casefold().str.contains(search, regex=False)
        | current["student_upn"].str.casefold().str.contains(search, regex=False)
    ]
if current.empty:
    st.write("Sin coincidencias.")
    connection.close()
    st.stop()

labels = {
    int(row.student_id): f"{row.student_name} · {row.career} · {row.group_name}"
    for row in current.itertuples()
}
student_id = st.selectbox("Estudiante", list(labels), format_func=labels.get)
submissions = students[students["student_id"] == student_id]
student = submissions.iloc[0]

st.subheader("Datos administrativos")
columns = st.columns(4)
columns[0].markdown(f"**Nombre**  \n{student['student_name']}")
columns[1].markdown(f"**Correo**  \n{student['student_upn']}")
columns[2].markdown(f"**Carrera**  \n{student['career']}")
columns[3].markdown(f"**Grupo**  \n{student['group_name']}")

if len(submissions) > 1:
    st.warning("Este alumno tiene varios envíos. Elige cuál es el vigente.")
    submission_labels = {
        int(row.submission_id): (
            f"Envío {row.submitted_at}" + (" · vigente" if row.is_current else "")
        )
        for row in submissions.itertuples()
    }
    chosen = st.radio(
        "Envíos", list(submission_labels), format_func=submission_labels.get
    )
    if not submissions.loc[
        submissions["submission_id"] == chosen, "is_current"
    ].iloc[0] and st.button("Marcar como vigente"):
        set_current_submission(connection, chosen)
        st.rerun()
    submission_id = chosen
else:
    submission_id = int(student["submission_id"])

st.subheader("Resultados por área")
results = area_results_frame(connection, engine)
results = results[results["submission_id"] == submission_id]
if results.empty:
    st.write("Este envío no tiene resultados de la versión activa.")
else:
    chart = results.assign(
        score=results["normalized_score"].fillna(0).round(1)
    )
    st.plotly_chart(
        px.bar(
            chart,
            x="score",
            y="area_name",
            color="traffic_light",
            orientation="h",
            range_x=[0, 100],
            color_discrete_map=LIGHT_COLORS,
            labels={"score": "Puntaje", "area_name": "Área", "traffic_light": ""},
        ),
        width="stretch",
    )
    recommendations = {
        recommendation.recommendation_code: recommendation
        for recommendation in engine.recommendations
    }
    for row in results.itertuples():
        recommendation = recommendations.get(row.recommendation_code)
        score = (
            f"{row.normalized_score:.1f}" if row.is_complete else "incompleta"
        )
        with st.expander(f"{row.area_name} · {score} · {row.traffic_light}"):
            if recommendation is None:
                st.write("Área incompleta: requiere revisión antes de recomendar.")
            else:
                st.markdown(
                    f"**Para el alumno:** {recommendation.student_recommendation}"
                )
                st.markdown(
                    f"**Para el personal:** {recommendation.staff_recommendation}"
                )

st.subheader("Alertas detonadas")
alerts = submission_alerts(connection, submission_id, engine.alerts.version)
if alerts.empty:
    st.write("Sin alertas.")
else:
    st.dataframe(
        alerts.rename(
            columns={
                "question_code": "Reactivo",
                "trigger_response": "Respuesta",
                "alert_level": "Nivel",
                "alert_category": "Categoría",
                "alert_reason": "Motivo",
                "suggested_action": "Acción sugerida",
            }
        ).drop(columns="rule_code"),
        hide_index=True,
        width="stretch",
    )

st.subheader("Caso y seguimiento")
case = submission_case(connection, submission_id)
if case is None:
    st.write("No hay caso abierto para este envío.")
else:
    columns = st.columns(4)
    columns[0].metric("Nivel", case["case_level"])
    columns[1].metric("Estado", case["case_status"])
    columns[2].metric("Contacto", case["contact_status"])
    columns[3].metric("Responsable", case["assigned_to"] or "—")
    st.caption(
        f"Fuente: {case['case_source']} · próximo seguimiento: "
        f"{case['next_follow_up_at'] or '—'} · gestionar en la página Casos."
    )
    notes = case_notes(connection, case["id"])
    for note in notes.itertuples():
        st.markdown(f"**{note.author}** · {note.created_at[:16]}  \n{note.note}")

responses = submission_responses(connection, submission_id, question_texts())
connection.close()
with st.expander("Respuestas no sensibles"):
    st.dataframe(
        responses.loc[~responses["is_sensitive"], RESPONSE_COLUMNS],
        hide_index=True,
        width="stretch",
    )
st.subheader("Respuestas sensibles")
st.caption(
    "Información confidencial. No compartir, copiar ni capturar fuera de "
    "Orientación y Tutorías."
)
if st.toggle("Mostrar respuestas sensibles", value=False):
    st.dataframe(
        responses.loc[responses["is_sensitive"], RESPONSE_COLUMNS],
        hide_index=True,
        width="stretch",
    )
st.caption("Los reportes PDF se generan desde la página Reportes.")
