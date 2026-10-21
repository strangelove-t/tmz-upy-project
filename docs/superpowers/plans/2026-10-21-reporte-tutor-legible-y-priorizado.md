# Reportes legibles para tutoría — plan de implementación

> **Para agentes:** ejecutar las tareas en orden con TDD y datos sintéticos.

**Objetivo:** hacer útil el PDF grupal para tutores sin exponer motivos ni
diagnósticos y nombrar los archivos con grupo o alumno.

**Arquitectura:** `group_report.py` sigue construyendo el modelo y PDF;
`reports.py` nombra archivos individuales; `5_Reportes.py` previsualiza el
mismo modelo. Los textos de guía viven en `report_content.yaml`.

**Tecnología:** SQLite, Streamlit, ReportLab, pytest.

## 1. Lista priorizada y privacidad

- [x] Ampliar `tests/test_group_report.py` con casos sintéticos abiertos y
  cerrados. Afirmar el mismo orden que `repository.cases_frame`, los cuatro
  campos autorizados y ausencia de correo, motivos, respuestas y diagnósticos.
- [x] Verificar el fallo de esas pruebas.
- [x] Añadir al modelo de `group_report.py` una lista de alumnos con caso
  abierto construida con las columnas de triage existentes y `triage_key`.
  Mantener el filtro de respuesta vigente, versión activa y umbral grupal.
- [x] Ejecutar las pruebas dirigidas hasta pasar.

## 2. Explicaciones y PDF

- [x] Añadir pruebas que extraigan texto del PDF: título con grupo,
  explicaciones de semáforo, niveles, áreas y lista; sin «resultados
  completos» ni información excluida.
- [x] Verificar el fallo; añadir los textos de niveles a
  `config/report_content.yaml` y reutilizar descripciones/leyenda existentes.
- [x] Reorganizar `render_group_pdf` con encabezados claros y tabla de alumnos
  con encabezado repetido si cambia de página; verificar las pruebas.

## 3. Pantalla y nombres de archivo

- [x] Cambiar `tests/test_pages.py` para exigir que desaparezca la métrica de
  cobertura, aparezcan las explicaciones y la lista priorizada.
- [x] Cambiar `tests/test_reports.py` para exigir nombre completo en los
  archivos de alumno y tutor y unicidad sin caracteres peligrosos.
- [x] Verificar fallos; actualizar `5_Reportes.py`, `reports.py` y las pruebas
  existentes de nombres de archivo. Mantener la descarga grupal en memoria.

## 4. Documentar y cerrar

- [x] Actualizar `README.md` y `docs/OPERACION_LOCAL.md` para declarar que el
  reporte grupal contiene nombres y explicar su entrega confidencial.
- [x] Correr suite completa, Ruff, compilación y `git diff --check`.
- [x] Renderizar PDFs sintéticos, revisar todas las páginas, eliminar
  temporales y presentar el resultado para integración local.
