from datetime import datetime
from pathlib import Path

import streamlit as st

from tamizaje import ui
from tamizaje.database import connect_database, record_export
from tamizaje.reports import (
    ReportError,
    build_report_data,
    export_batch,
    generate_report,
    load_template,
)
from tamizaje.repository import students_frame
from tamizaje.student_report import (
    build_student_view,
    contact_line,
    scale_note,
    score_text,
)
from tamizaje.ui import (
    NO_SUBMISSIONS,
    page_header,
    require_context,
    show_sensitive_summary,
)

page_header(
    "Reportes",
    "Sólo incluyen campos autorizados: el del alumno no lleva alertas ni notas "
    "internas; el del tutor sólo incluye condiciones declaradas si lo autorizas.",
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


def show_student_preview(data: dict) -> None:
    """Mismo contenido y orden que el PDF del alumno."""
    view = build_student_view(data, data["student_labels"])
    st.write(data["student_introduction"])
    labels = data["student_labels"]
    columns = st.columns(3)
    for column, level in zip(columns, ("Verde", "Amarillo", "Rojo"), strict=True):
        column.metric(labels[level], view.counts[level])
    st.caption(scale_note(data.get("score_scale")))
    st.dataframe(
        [
            {
                "Área": item.area_name,
                "Cifra": score_text(item.score),
                "Resultado": item.label,
            }
            for item in view.areas
        ],
        hide_index=True,
        width="stretch",
    )
    if view.focus:
        st.markdown("**Qué te recomendamos**")
        for area_name, text, _level in view.focus:
            st.markdown(f"**{area_name}:** {text}")
    if contact := contact_line(data):
        st.caption(f"Orientación y Tutorías: {contact}")


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


individual_tab, batch_tab = st.tabs(["Individual", "Por lote"])

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
            "Incluir condiciones de salud, neurodivergencias y diagnósticos "
            "declarados",
            value=False,
            key="include_sensitive_report",
        )
        if include_sensitive:
            st.warning(
                "El PDF incluirá información sensible. Compártelo únicamente "
                "con personal autorizado de Orientación y Tutorías."
            )

    try:
        template = load_template(report_type)
        data = build_report_data(
            connection,
            submission_id,
            engine,
            template,
            include_sensitive=include_sensitive,
        )
        filename, content = generate_report(
            connection,
            submission_id,
            engine,
            report_type,
            include_sensitive=include_sensitive,
        )
    except ReportError as error:
        st.error(f"No fue posible generar el reporte: {error}")
    else:
        with st.container(border=True):
            st.subheader(f"Vista previa · {template.title}")
            st.caption(
                " · ".join(
                    str(data[field])
                    for field in ("student_name", "career", "group_name")
                    if field in data
                )
            )
            if report_type == "student":
                show_student_preview(data)
            else:
                st.write(data.get("introduction", ""))
                st.markdown("**Cómo leer el semáforo**")
                for label, explanation in data.get(
                    "traffic_light_legend", {}
                ).items():
                    st.markdown(f"**{label}:** {explanation}")
                for line in data["areas"]:
                    status = line.traffic_light or "Pendiente de revisión"
                    with st.expander(f"{line.area_name} · {status}"):
                        st.write(line.description)
                        st.metric(
                            "Puntaje",
                            f"{line.score:.1f} de 100"
                            if line.score is not None
                            else "—",
                        )
                        st.write(line.interpretation)
                for area_name, text in data.get("recommendations", []):
                    st.markdown(f"**{area_name}:** {text}")
            if "sensitive_summary" in data:
                show_sensitive_summary(data["sensitive_summary"])
            st.caption(template.disclaimer)
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

with batch_tab:
    st.warning(
        "Los reportes por lote contienen información confidencial de todos los "
        "alumnos. Se guardan sólo en esta computadora; entrégalos únicamente por "
        "canales institucionales autorizados."
    )
    st.write(
        f"Genera el reporte del alumno y el expediente para tutor de "
        f"{len(students)} alumnos, más una lista de qué archivo corresponde a "
        "cada correo."
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
connection.close()
