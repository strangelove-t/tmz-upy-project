# Vista previa y recomendaciones individuales — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que las vistas previas reflejen el contenido de los PDF y permitir ajustes temporales de recomendaciones en los reportes individuales.

**Architecture:** `reports.py` aplica cambios por código de área sobre una copia de los datos autorizados. `pages/5_Reportes.py` conserva los textos sólo en la sesión activa y usa ese único resultado para vista previa y PDF. El reporte grupal sigue usando `GroupReport`, y la exportación por lote no recibe ediciones.

**Tech Stack:** Python 3.13, Streamlit, ReportLab, SQLite, pytest/AppTest, Ruff.

---

## Mapa de archivos

- `src/tamizaje/reports.py`: transformación pura de recomendaciones; nombre y renderizado del PDF individual.
- `pages/5_Reportes.py`: controles temporales y vistas previas de alumno, tutor y grupo.
- `tests/test_reports.py`: contrato de transformación, aislamiento y texto del PDF sintético.
- `tests/test_pages.py`: comportamiento de la UI y sus límites de privacidad.
- `docs/OPERACION_LOCAL.md` y `README.md`: instrucción operativa de edición y alcance.

## 1. Transformación sin mutar el catálogo

- [ ] Añadir en `tests/test_reports.py` una prueba con un alumno sintético que obtiene `build_report_data`, aplica `apply_recommendation_edits(data, {codigo: texto}, tipo)` y afirma texto nuevo en `areas` y `recommendations`, originales sin cambios y `engine.recommendations` intacto.
- [ ] Correr `.venv/bin/pytest -q tests/test_reports.py::test_recommendation_edit_only_changes_copy` y confirmar fallo por función ausente.
- [ ] Implementar en `reports.py` una función pura que valida tipo, código editable y texto no vacío, reconstruye `AreaLine` con `dataclasses.replace` y devuelve un nuevo diccionario con `areas` y `recommendations` concordantes. Para `student`, sólo amarillo/rojo; para `tutor`, también verde. El texto se normaliza con `" ".join(text.split())` y se escapa al renderizar PDF mediante los renderizadores existentes.
- [ ] Añadir pruebas de código ajeno, área pendiente, texto en blanco y HTML literal; correr `tests/test_reports.py` hasta verde.

## 2. Un único contenido para editar, previsualizar y descargar

- [ ] Añadir en `tests/test_pages.py` una prueba AppTest: un `text_area` editable en Individual cambia la recomendación visible y los bytes del botón PDF; al cambiar alumno o destinatario se restablece el texto original. Confirmar fallo.
- [ ] En `pages/5_Reportes.py`, cargar la plantilla y `build_report_data` una sola vez por ejecución. Guardar los `text_area` de las áreas aplicables en `st.session_state` y descartar sus claves al cambiar `(submission_id, report_type)`. El control de información sensible conserva su reinicio actual, y la casilla no borra las ediciones del tutor.
- [ ] Aplicar la función pura al contenido, renderizar con `render_pdf` y construir el nombre con `report_filename` y `external_response_id`. No usar `generate_report` por segunda vez desde la página; mantener `generate_report` para lotes. Añadir botón de restauración mediante callback de Streamlit.
- [ ] Si hay texto vacío o falla el renderizado, mostrar error y no crear `download_button`. Añadir pruebas para ese caso, la restauración, tutor sensible apagado y lote no alterado; correr `tests/test_pages.py`.

## 3. Concordancia de secciones y orden

- [ ] Añadir pruebas AppTest que exijan las secciones del PDF del alumno (resumen, áreas con descripción, acciones, fortalezas, recursos, aviso), del tutor (resumen, leyenda, áreas, acciones y bloque sensible sólo autorizado) y del grupo (solicitudes de contacto, guía, focos y aviso). Confirmar fallos.
- [ ] Ampliar las funciones de vista previa en `pages/5_Reportes.py` usando los modelos existentes `build_student_view`, `AreaLine` y `GroupReport`. Mostrar encabezado/fecha y el mismo orden que cada PDF. No mostrar diagnósticos en alumno ni en grupo.
- [ ] Extraer texto de PDF sintéticos con `pdftotext` cuando esté instalado y comparar recomendaciones editadas y títulos/secciones con la vista previa; correr `tests/test_pages.py`, `tests/test_reports.py` y `tests/test_group_report.py`.

## 4. Documentación, revisión y cierre

- [ ] Documentar en `README.md` y `docs/OPERACION_LOCAL.md` que las ediciones son temporales, sólo afectan al reporte individual activo, se restablecen al cambiar de contexto y no modifican catálogo ni lotes. Aclarar que vista previa coincide en contenido, no en paginación.
- [ ] Ejecutar `.venv/bin/pytest -q`, `.venv/bin/ruff check .`, `python -m compileall -q app.py pages src` y `git diff --check`.
- [ ] Revisar PDF sintéticos de alumno, tutor y grupo y contrastar con las vistas previas. Verificar que ningún dato real se use en pruebas o se imprima en registros.
- [ ] Revisar el diff sólo de los archivos de esta función; no incorporar `config/recommendations.csv`, `tests/test_recommendations.py` ni `tests/test_dependencies.py`, que ya tenían cambios locales.

**Puntos de control:** cada bloque debe quedar en verde antes de continuar. No hay migración de datos ni nuevas dependencias.
