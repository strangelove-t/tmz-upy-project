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
from tamizaje.ui import (
    DISCLAIMER,
    LIGHT_COLORS,
    LIGHT_ORDER,
    NO_SUBMISSIONS,
    format_date,
    page_header,
    question_texts,
    require_context,
    status_row,
)

RESPONSE_COLUMNS = {
    "question_code": "Reactivo",
    "question_text": "Pregunta",
    "response_raw": "Respuesta",
}

page_header(
    "Estudiantes", "Expediente individual: resultados, seguimiento y respuestas."
)

engine, connection = require_context()
students = students_frame(connection)
if students.empty:
    st.info(NO_SUBMISSIONS)
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
    st.info("Sin resultados para esta búsqueda. Revisa el nombre o el correo.")
    connection.close()
    st.stop()

labels = {
    int(row.student_id): f"{row.student_name} · {row.career} · {row.group_name}"
    for row in current.itertuples()
}
student_id = st.selectbox("Estudiante", list(labels), format_func=labels.get)
submissions = students[students["student_id"] == student_id]
student = submissions.iloc[0]

with st.container(border=True):
    st.subheader(student["student_name"])
    st.caption(
        f"{student['career']} · Grupo {student['group_name']} · "
        f"{student['student_upn']}"
    )

    if len(submissions) > 1:
        st.warning(
            f"Este alumno respondió el cuestionario {len(submissions)} veces. "
            "Elige cuál respuesta es la válida: sólo esa aparece en Casos, "
            "Grupos y Reportes."
        )
        submission_labels = {
            int(row.submission_id): (
                f"Respuesta del {format_date(row.submitted_at)}"
                + (" — la válida" if row.is_current else "")
            )
            for row in submissions.itertuples()
        }
        submission_id = st.radio(
            "Respuestas recibidas",
            list(submission_labels),
            format_func=submission_labels.get,
        )
        is_current = bool(
            submissions.loc[
                submissions["submission_id"] == submission_id, "is_current"
            ].iloc[0]
        )
        if not is_current and st.button("Usar esta respuesta como la válida"):
            set_current_submission(connection, submission_id)
            st.rerun()
    else:
        submission_id = int(student["submission_id"])

    if st.button("Ver reportes del alumno", icon=":material/description:"):
        st.session_state["reports_target"] = submission_id
        connection.close()
        st.switch_page("pages/5_Reportes.py")

results = area_results_frame(connection, engine)
results = results[results["submission_id"] == submission_id]
alerts = submission_alerts(connection, submission_id, engine.alerts.version)
case = submission_case(connection, submission_id)
notes = case_notes(connection, case["id"]) if case else None
responses = submission_responses(connection, submission_id, question_texts())
connection.close()

results_tab, follow_up_tab, responses_tab = st.tabs(
    ["Resultados", "Seguimiento", "Respuestas"]
)

with results_tab:
    if results.empty:
        st.info("Aún no hay resultados para esta respuesta.")
    else:
        chart = results.assign(
            score=results["normalized_score"].fillna(0).round(1),
            label=results.apply(
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
        st.plotly_chart(figure, width="stretch")

        strengths = results[results["traffic_light"] == "Verde"]
        opportunities = results[results["traffic_light"].isin(["Amarillo", "Rojo"])]
        incomplete = results[results["is_complete"] == 0]
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
        for row in results.itertuples():
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
    if case is None:
        st.info("Esta respuesta no generó alertas; no hay caso de seguimiento.")
    else:
        if not case.get("is_active", 1):
            st.caption(
                "Este caso ya no tiene alertas vigentes; se conserva como historial."
            )
        status_row(
            {
                "Nivel": case["case_level"],
                "Estado": case["case_status"],
                "Contacto": case["contact_status"],
                "Responsable": case["assigned_to"] or "—",
            }
        )
        st.caption(
            f"Fuente: {case['case_source']} · próximo seguimiento: "
            f"{format_date(case['next_follow_up_at'])}"
        )
        st.page_link(
            "pages/2_Casos.py",
            label="Actualizar el seguimiento en Casos",
            icon=":material/assignment:",
        )
        st.markdown("**Alertas detonadas**")
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
        st.markdown("**Notas**")
        if notes is None or notes.empty:
            st.caption("Sin notas.")
        else:
            for note in notes.itertuples():
                st.markdown(
                    f"**{note.author}** · "
                    f"{format_date(note.created_at, engine.report_timezone)}"
                    f"  \n{note.note}"
                )

with responses_tab:
    with st.expander("Respuestas no sensibles"):
        st.dataframe(
            responses.loc[~responses["is_sensitive"], list(RESPONSE_COLUMNS)].rename(
                columns=RESPONSE_COLUMNS
            ),
            hide_index=True,
            width="stretch",
        )
    st.warning(
        "Las respuestas sensibles son confidenciales. No las compartas, copies ni "
        "captures fuera de Orientación y Tutorías."
    )
    if st.toggle("Mostrar respuestas sensibles", value=False):
        st.dataframe(
            responses.loc[responses["is_sensitive"], list(RESPONSE_COLUMNS)].rename(
                columns=RESPONSE_COLUMNS
            ),
            hide_index=True,
            width="stretch",
        )

st.caption(DISCLAIMER)
