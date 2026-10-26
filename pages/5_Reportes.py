from datetime import datetime
from pathlib import Path

import streamlit as st

from tamizaje import reports as report_service
from tamizaje import ui
from tamizaje.database import connect_database, record_export
from tamizaje.group_report import (
    GROUP_AREAS_NOTE,
    GROUP_CONFIDENTIALITY_NOTE,
    GROUP_ROSTER_NOTE,
    GroupReportError,
    build_group_report,
    group_report_filename,
    render_group_pdf,
)
from tamizaje.pdf_brand import LEVELS, PENDING
from tamizaje.report_edits import (
    MAX_TEXT_LENGTH,
    EditableField,
    ReportEditError,
    apply_edits,
    clear_edits,
    editable_fields,
    group_subject,
    last_edited_at,
    load_edits,
    save_edits,
)
from tamizaje.reports import (
    ReportError,
    apply_recommendation_edits,
    build_report_data,
    export_batch,
    load_template,
    report_filename,
)
from tamizaje.repository import students_frame
from tamizaje.student_report import (
    STRENGTHS_SUFFIX,
    build_student_view,
    contact_line,
    join_area_names,
    score_text,
    student_area_note,
)
from tamizaje.ui import (
    NO_SUBMISSIONS,
    format_date,
    page_header,
    require_context,
    show_sensitive_summary,
)

page_header(
    "Reportes",
    "Revisa la vista previa, ajusta los textos o agrega notas y descarga el PDF. "
    "Las cifras y semáforos vienen del cuestionario y no se editan.",
)

engine, connection = require_context()
students = students_frame(connection)
students = students[students["is_current"] == 1]
if students.empty:
    st.info(NO_SUBMISSIONS)
    connection.close()
    st.stop()

REPORT_LABELS = {
    "student": "Reporte del alumno",
    "tutor": "Expediente para tutor",
}
NOTES_WARNINGS = {
    "student": "El alumno leerá este mensaje. No escribas diagnósticos, alertas "
    "ni información de otras personas.",
    "tutor": "Las notas se imprimen en el expediente que recibe el tutor.",
    "group": "Las notas se imprimen en el informe que recibe el tutor del grupo.",
}


def show_student_preview(data: dict) -> None:
    """Resultados del PDF del alumno; los textos se editan debajo."""
    view = build_student_view(data, data["student_labels"])
    st.write(data["student_introduction"])
    st.subheader("Tu resumen")
    labels = data["student_labels"]
    columns = st.columns(3)
    for column, level in zip(columns, ("Verde", "Amarillo", "Rojo"), strict=True):
        column.metric(labels[level], view.counts[level])
    st.subheader("Tus resultados por área")
    st.caption(student_area_note(data.get("score_scale")))
    st.dataframe(
        [
            {
                "Área": item.area_name,
                "Qué observa": item.description,
                "Cifra": score_text(item.score),
                "Resultado": item.label,
            }
            for item in view.areas
        ],
        hide_index=True,
        width="stretch",
    )
    if view.focus:
        st.subheader("Qué te recomendamos")
        for area_name, text, _level in view.focus:
            st.markdown(f"**{area_name}**")
            st.text(text)
    if view.strengths:
        st.subheader("Tus fortalezas")
        st.write(f"Destacas en {join_area_names(view.strengths)}. {STRENGTHS_SUFFIX}")
    if view.missing:
        st.caption(
            "No tuvimos información suficiente para interpretar "
            + ", ".join(view.missing)
            + ". Si quieres, platícalo con Orientación y Tutorías."
        )
    if data.get("notes"):
        st.subheader("Mensaje de Orientación y Tutorías")
        st.write(data["notes"])
    st.subheader("¿Con quién puedes hablar?")
    for resource in data.get("resources", []):
        st.write(f"• {resource}")
    if contact := contact_line(data):
        st.write(f"Orientación y Tutorías: {contact}")


def show_tutor_preview(data: dict) -> None:
    """Secciones del expediente en el mismo orden que el PDF."""
    st.write(data.get("introduction", ""))
    lines = sorted(
        data["areas"],
        key=lambda line: (
            LEVELS[line.traffic_light if line.traffic_light in LEVELS else PENDING][2],
            line.area_code,
        ),
    )
    st.subheader("Resumen")
    counts = st.columns(3)
    for column, level in zip(counts, ("Verde", "Amarillo", "Rojo"), strict=True):
        column.metric(
            f"Áreas en {level.lower()}",
            sum(line.traffic_light == level for line in lines),
        )
    st.subheader("Cómo leer el semáforo")
    for label, explanation in data.get("traffic_light_legend", {}).items():
        st.markdown(f"**{label}:** {explanation}")
    st.subheader("Resultados por área")
    st.caption(
        "Cifra de 0 a 100 por área. Primero aparecen las áreas que conviene atender."
    )
    for line in lines:
        status = line.traffic_light or "Pendiente de revisión"
        with st.expander(f"{line.area_name} · {status}"):
            st.write(line.description)
            st.metric("Cifra", score_text(line.score))
            st.write(line.interpretation)
    recommendations = {
        line.area_name: line.recommendation for line in lines if line.recommendation
    }
    if recommendations:
        st.subheader("Acciones sugeridas para la tutoría")
        focus = [
            line
            for line in lines
            if line.traffic_light in ("Rojo", "Amarillo") and line.recommendation
        ]
        strengths = [
            line
            for line in lines
            if line.traffic_light == "Verde" and line.recommendation
        ]
        if not focus:
            st.caption("Ninguna área está en amarillo o rojo.")
        for line in focus:
            st.markdown(f"**{line.area_name}**")
            st.text(line.recommendation)
        if strengths:
            st.markdown("**Fortalezas para reconocer**")
            for line in strengths:
                st.markdown(f"**{line.area_name}**")
                st.text(line.recommendation)


def _area_of(key: str) -> str | None:
    return key.split(":", 1)[1] if ":" in key else None


def edit_form(
    report_type: str,
    subject: str,
    fields: list[EditableField],
    edits: dict[str, str],
    area_names: dict[str, str] | None = None,
) -> None:
    """Textos del reporte como campos editables; se guardan por alumno o grupo."""
    prefix = f"edit_{report_type}_{subject}"
    keys = {field.key: f"{prefix}_{field.key}" for field in fields}
    if st.session_state.pop(f"{prefix}_saved", False):
        st.success("Cambios guardados. El PDF de arriba ya los incluye.")
    edited_at = last_edited_at(connection, report_type, subject)
    if edited_at:
        st.info(
            "Este reporte tiene textos editados o notas (último cambio: "
            f"{format_date(edited_at, engine.report_timezone)})."
        )

    def text_area(field: EditableField) -> None:
        st.text_area(
            field.label,
            value=edits.get(field.key, field.default),
            key=keys[field.key],
            max_chars=MAX_TEXT_LENGTH,
            height=120 if field.key == "notes" else 90,
        )

    general = [f for f in fields if _area_of(f.key) is None and f.key != "notes"]
    by_area: dict[str, list[EditableField]] = {}
    for field in fields:
        if (code := _area_of(field.key)) is not None:
            by_area.setdefault(code, []).append(field)
    notes = next(field for field in fields if field.key == "notes")

    with st.form(f"{prefix}_form", border=False):
        st.markdown("**Textos del reporte**")
        for field in general:
            text_area(field)
        if by_area:
            st.markdown("**Textos por área**")
            for code, area_fields in by_area.items():
                changed = any(field.key in edits for field in area_fields)
                title = (area_names or {}).get(code, code)
                with st.expander(f"{title}{' · editado' if changed else ''}"):
                    for field in area_fields:
                        text_area(field)
        st.markdown("**Notas para el PDF**")
        st.caption(NOTES_WARNINGS[report_type])
        text_area(notes)
        submitted = st.form_submit_button(
            "Guardar cambios", type="primary", icon=":material/save:"
        )
    if submitted:
        values = {key: st.session_state[widget] for key, widget in keys.items()}
        try:
            save_edits(
                connection,
                report_type,
                subject,
                values,
                {field.key: field.default for field in fields},
            )
        except ReportEditError as error:
            st.error(str(error))
        else:
            for key in list(st.session_state):
                if key.startswith("recommendation_edit_"):
                    del st.session_state[key]
            st.session_state[f"{prefix}_saved"] = True
            st.rerun()
    if edited_at and st.button(
        "Restaurar textos originales y borrar notas",
        key=f"{prefix}_restore",
        icon=":material/restart_alt:",
    ):
        clear_edits(connection, report_type, subject)
        for key in list(st.session_state):
            if key.startswith("recommendation_edit_"):
                del st.session_state[key]
        for widget in keys.values():
            st.session_state.pop(widget, None)
        st.rerun()


def log_download(
    submission_id: int,
    report_type: str,
    filename: str,
    includes_sensitive: bool,
) -> None:
    log_connection = connect_database(ui.DATABASE_PATH)
    record_export(
        log_connection,
        submission_id,
        report_type,
        f"descarga:{filename}",
        load_template(report_type).template_version,
        includes_sensitive_summary=includes_sensitive,
    )
    log_connection.close()


def restore_recommendations(originals: dict[str, str]) -> None:
    for code, value in originals.items():
        st.session_state[f"recommendation_edit_{code}"] = value


def edit_recommendations(data: dict, report_type: str, submission_id: int) -> dict:
    context = (submission_id, report_type)
    if st.session_state.get("recommendation_edit_context") != context:
        for key in list(st.session_state):
            if key.startswith("recommendation_edit_"):
                del st.session_state[key]
        st.session_state["recommendation_edit_context"] = context

    editable = [
        line
        for line in data["areas"]
        if line.recommendation
        and (report_type == "tutor" or line.traffic_light in ("Amarillo", "Rojo"))
    ]
    if not editable:
        return data
    originals = {line.area_code: line.recommendation for line in editable}
    with st.expander("Editar recomendaciones de este reporte"):
        st.caption(
            "Los cambios son temporales y sólo afectan este PDF. "
            "No incluyas diagnósticos en el reporte del alumno."
        )
        for line in editable:
            key = f"recommendation_edit_{line.area_code}"
            if key not in st.session_state:
                st.session_state[key] = line.recommendation
            st.text_area(f"Recomendación · {line.area_name}", key=key)
        st.button(
            "Restaurar recomendaciones originales",
            on_click=restore_recommendations,
            args=(originals,),
        )
    edits = {
        code: st.session_state[f"recommendation_edit_{code}"]
        for code, original in originals.items()
        if st.session_state[f"recommendation_edit_{code}"] != original
    }
    return apply_recommendation_edits(data, edits, report_type)


individual_tab, group_tab, batch_tab = st.tabs(["Individual", "Grupal", "Por lote"])

with individual_tab:
    labels = {
        int(row.submission_id): (
            f"{row.student_name} · {row.career} · {row.group_name}"
        )
        for row in students.itertuples()
    }
    ids = list(labels)
    # Llegada desde el expediente: preselecciona al mismo alumno.
    target = st.session_state.pop("reports_target", None)
    columns = st.columns([2, 1])
    submission_id = columns[0].selectbox(
        "Estudiante",
        ids,
        index=ids.index(target) if target in ids else 0,
        format_func=labels.get,
        key="report_student",
    )
    report_type = columns[1].radio(
        "Tipo de reporte",
        list(REPORT_LABELS),
        format_func=REPORT_LABELS.get,
        key="report_type",
    )
    include_sensitive = False
    if report_type == "tutor":
        report_context = (submission_id, report_type)
        if st.session_state.get("sensitive_report_context") != report_context:
            st.session_state["include_sensitive_report"] = False
            st.session_state["sensitive_report_context"] = report_context
        include_sensitive = st.checkbox(
            "Incluir condiciones de salud, neurodivergencias y diagnósticos declarados",
            value=False,
            key="include_sensitive_report",
        )
        if include_sensitive:
            st.warning(
                "El PDF incluirá información sensible. Compártelo únicamente "
                "con personal autorizado de Orientación y Tutorías."
            )

    subject = str(submission_id)
    try:
        template = load_template(report_type)
        original = build_report_data(
            connection,
            submission_id,
            engine,
            template,
            include_sensitive=include_sensitive,
        )
        edits = load_edits(connection, report_type, subject)
        data = apply_edits(original, report_type, edits)
        data = edit_recommendations(data, report_type, submission_id)
        external_id = connection.execute(
            "SELECT external_response_id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()[0]
        filename = report_filename(report_type, external_id, data["student_name"])
        try:
            content = report_service.render_pdf(data, template)
        except Exception as error:
            raise ReportError("El PDF no pudo renderizarse.") from error
    except ReportError as error:
        st.error(f"No fue posible generar el reporte: {error}")
    else:
        st.download_button(
            f"Descargar {REPORT_LABELS[report_type].lower()} (PDF)",
            content,
            file_name=filename,
            mime="application/pdf",
            on_click=log_download,
            args=(submission_id, report_type, filename, include_sensitive),
            type="primary",
            icon=":material/download:",
        )
        st.caption(
            "Revisa la vista previa antes de descargar. El PDF incluye los textos "
            "y notas guardados."
        )
        with st.container(border=True):
            st.subheader(f"Vista previa · {template.title}")
            st.caption(
                " · ".join(
                    str(data[field])
                    for field in ("student_name", "career", "group_name")
                    if field in data
                )
                + " · "
                + datetime.strptime(data["generated_at"], "%Y-%m-%d").strftime(
                    "%d/%m/%Y"
                )
            )
            if report_type == "student":
                show_student_preview(data)
            else:
                show_tutor_preview(data)
                if data.get("notes"):
                    st.subheader("Notas de Orientación")
                    st.write(data["notes"])
            if summary := data.get("sensitive_summary"):
                if summary.has_sensitive_declaration:
                    st.subheader("Condiciones y apoyos declarados")
                    show_sensitive_summary(summary)
            st.caption(data["disclaimer"])
            edit_form(
                report_type,
                subject,
                editable_fields(original, report_type),
                edits,
                {line.area_code: line.area_name for line in original["areas"]},
            )

with group_tab:
    st.write(
        "Informe para el tutor del grupo con tendencias generales y alumnos que "
        "requieren acompañamiento. No incluye correos, motivos ni diagnósticos."
    )
    st.warning(
        "El PDF contiene nombres de alumnos. Entrégalo sólo al tutor del grupo "
        "por un canal institucional autorizado."
    )
    selectors = st.columns(2)
    career = selectors[0].selectbox(
        "Carrera del reporte", sorted(students["career"].unique())
    )
    group_name = selectors[1].selectbox(
        "Grupo del reporte",
        sorted(students.loc[students["career"] == career, "group_name"].unique()),
    )
    try:
        original_group = build_group_report(connection, engine, career, group_name)
    except GroupReportError as error:
        st.warning(str(error))
    else:
        subject = group_subject(career, group_name)
        group_edits = load_edits(connection, "group", subject)
        group_report = apply_edits(original_group, "group", group_edits)
        st.download_button(
            "Descargar resumen grupal (PDF)",
            render_group_pdf(group_report),
            file_name=group_report_filename(group_report),
            mime="application/pdf",
            type="primary",
            icon=":material/download:",
        )
        st.caption(
            "Revisa la vista previa antes de descargar. El PDF incluye los textos "
            "y notas guardados."
        )
        with st.container(border=True):
            st.subheader("Resumen para el tutor del grupo")
            st.caption(
                f"Grupo {group_report.group_name} · Informe para el tutor del grupo · "
                f"{group_report.career} · {group_report.generated_at:%d/%m/%Y %H:%M}"
            )
            st.write(group_report.introduction)
            metrics = st.columns(3)
            metrics[0].metric("Alumnos evaluados", group_report.student_count)
            metrics[1].metric("Requieren acompañamiento", len(group_report.students))
            metrics[2].metric(
                "Pidieron contacto",
                sum(student.requested_contact for student in group_report.students),
            )
            st.subheader("Cómo leer los resultados")
            st.write(
                "Un semáforo resume los recursos observados en cada área; no es "
                "un diagnóstico ni describe por sí solo a cada alumno."
            )
            for light, explanation in group_report.traffic_light_legend.items():
                st.markdown(f"**{light}:** {explanation}")
            st.subheader("Niveles de atención")
            for level, explanation in group_report.level_explanations.items():
                st.markdown(
                    f"**{level} ({group_report.open_cases_by_level[level]}):** "
                    f"{explanation}"
                )
            st.subheader("Áreas del grupo")
            st.caption(GROUP_AREAS_NOTE)
            st.dataframe(
                [
                    {
                        "Área": area.name,
                        "Qué observa": area.description,
                        "Promedio": score_text(area.average),
                        "Verde": area.distribution["Verde"],
                        "Amarillo": area.distribution["Amarillo"],
                        "Rojo": area.distribution["Rojo"],
                        "Sin dato": area.distribution["Pendiente"],
                    }
                    for area in group_report.areas
                ],
                hide_index=True,
                width="stretch",
            )
            st.markdown("**Áreas para iniciar la conversación**")
            if group_report.focus_areas:
                for area in group_report.focus_areas:
                    plural = "alumno" if area.attention_count == 1 else "alumnos"
                    st.write(
                        f"{area.name}: {area.attention_count} {plural} en amarillo o "
                        f"rojo. {area.description}"
                    )
            else:
                st.write("No hay áreas con semáforo amarillo o rojo.")
            if group_report.notes:
                st.subheader("Notas para el tutor")
                st.write(group_report.notes)
            st.subheader("Alumnos que requieren acompañamiento")
            st.caption(GROUP_ROSTER_NOTE)
            if group_report.students:
                st.dataframe(
                    [
                        {
                            "#": index,
                            "Alumno": student.name,
                            "Nivel": student.level,
                            "Alertas": student.alert_count,
                            "Pidió contacto": (
                                "Sí" if student.requested_contact else "No"
                            ),
                        }
                        for index, student in enumerate(
                            group_report.students, start=1
                        )
                    ],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("No hay alumnos con atención abierta en este grupo.")
            st.caption(GROUP_CONFIDENTIALITY_NOTE)
            edit_form(
                "group",
                subject,
                editable_fields(original_group, "group"),
                group_edits,
            )

with batch_tab:
    st.warning(
        "Los reportes por lote contienen información confidencial de todos los "
        "alumnos. Se guardan sólo en esta computadora; entrégalos únicamente por "
        "canales institucionales autorizados."
    )
    confirm = st.checkbox("Entiendo que los archivos generados son confidenciales.")
    batch_sensitive = st.checkbox(
        "Incluir condiciones y diagnósticos declarados en todos los expedientes "
        "para tutor",
        value=False,
    )
    sensitive_confirm = st.checkbox(
        "Confirmo que los tutores están autorizados para recibir esta información.",
        value=False,
        disabled=not batch_sensitive,
    )
    if st.button(
        "Generar todos los reportes",
        disabled=not confirm or (batch_sensitive and not sensitive_confirm),
        type="primary",
        icon=":material/picture_as_pdf:",
    ):
        output_dir = ui.EXPORTS_DIR / datetime.now(engine.report_timezone).strftime(
            "%Y%m%d-%H%M%S"
        )
        with st.spinner("Generando reportes…"):
            manifest = export_batch(
                connection,
                engine,
                output_dir,
                include_sensitive_tutor=batch_sensitive,
            )
        st.session_state["manifest"] = str(manifest)
    if "manifest" in st.session_state:
        manifest_path = Path(st.session_state["manifest"])
        if manifest_path.exists():
            pdf_count = len(list(manifest_path.parent.glob("*.pdf")))
            st.success(
                f"Se generaron {pdf_count} PDF y el manifiesto en la carpeta local "
                f"{manifest_path.parent}"
            )
            st.download_button(
                "Descargar manifiesto",
                manifest_path.read_bytes(),
                file_name="manifiesto.csv",
                mime="text/csv",
            )

    with st.container(border=True):
        st.subheader("Vista previa del lote")
        st.write(
            f"Se generarán el reporte del alumno y el expediente para tutor de "
            f"{len(students)} alumnos, más una lista de qué archivo corresponde a "
            "cada correo. Los PDF incluyen los textos y notas guardados de cada "
            "alumno; para revisarlos o cambiarlos usa la pestaña **Individual**."
        )
        edited = {
            (report_type, subject)
            for report_type, subject in connection.execute(
                "SELECT DISTINCT report_type, subject FROM report_edits "
                "WHERE report_type IN ('student', 'tutor')"
            )
        }
        st.dataframe(
            [
                {
                    "Alumno": row.student_name,
                    "Grupo": row.group_name,
                    "Reporte del alumno": (
                        "Editado"
                        if ("student", str(row.submission_id)) in edited
                        else "Original"
                    ),
                    "Expediente para tutor": (
                        "Editado"
                        if ("tutor", str(row.submission_id)) in edited
                        else "Original"
                    ),
                }
                for row in students.itertuples()
            ],
            hide_index=True,
            width="stretch",
        )
connection.close()
