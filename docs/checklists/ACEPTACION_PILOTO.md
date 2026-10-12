# Checklist de aceptación del piloto

> **Importación real bloqueada.** No procesar las líneas 16 en adelante
> mientras la última casilla de este documento esté sin marcar.

Este documento no debe contener nombres, correos, respuestas ni diagnósticos.
Registra sólo conteos, fechas, versiones y resultados.

- Fecha de ejecución: ____________
- Commit evaluado: ____________
- Versiones: cuestionario ____ · scoring ____ · reglas ____

## A. Controles técnicos

Marcados por el equipo de desarrollo con evidencia de comandos.

### Acceso

- [x] La aplicación sólo escucha en `127.0.0.1:8501`.
- [x] Sin contraseña configurada, la aplicación queda bloqueada.
- [x] Una contraseña incorrecta se rechaza.
- [x] La contraseña correcta da acceso.
- [x] **Cerrar sesión** vuelve a pedir la contraseña.
- [x] Ninguna página consulta la base antes de autenticar.
- [x] `.streamlit/secrets.toml` está ignorado y no hay contraseña en Git.

### Piloto con las líneas 2–15

- [ ] Se procesaron exactamente 14 registros (líneas 2–15).
- [ ] Mapeo de encabezados válido (105 columnas).
- [ ] Scoring: 126 resultados de área calculados.
- [ ] Alertas y casos calculados sin errores.
- [ ] Recálculo de los 14 envíos sin errores.
- [x] Umbral de confidencialidad de grupos verificado (pruebas automatizadas).
- [ ] 28 PDF generados y estructuralmente válidos.
- [ ] La base y los PDF temporales se eliminaron al terminar.
- [ ] La salida de consola no contiene datos personales.

### Operación

- [x] Respaldo de la base probado con una base sintética.
- [x] Restauración probada con una base sintética.
- [x] Suite automatizada, Ruff y compilación aprobados.
- [x] `git ls-files data exports .streamlit/secrets.toml` sólo muestra los
      `.gitkeep`.

### Evidencia técnica (2026-10-08, rama `feature/local-access-pilot`)

- Streamlit anunció `URL: http://127.0.0.1:8501`; `ss -ltn` mostró sólo
  `127.0.0.1:8501` y la IP de red del equipo no respondió.
- Acceso: `tests/test_auth.py`, `tests/test_app.py` y
  `test_pages_require_authentication_before_reading` (seis páginas).
- `git check-ignore .streamlit/secrets.toml` lo reporta como ignorado;
  `git ls-files data exports .streamlit/secrets.toml` sólo lista
  `data/.gitkeep` y `exports/.gitkeep`.
- `scripts/run_acceptance.py` con un CSV **sintético** de 17 registros:
  líneas 2–15, 14 envíos, 126 resultados de área (126 completos), 14
  recalculados, 28 PDF validados, temporales eliminados, `APROBADO`, sin datos
  personales en la consola. Las casillas del piloto quedan pendientes hasta
  ejecutarlo con el archivo local en la computadora autorizada.
- Respaldo y restauración: copia, sustitución y `PRAGMA integrity_check = ok`
  sobre una base sintética (equivalente Linux de los comandos de
  `docs/OPERACION_LOCAL.md`; falta repetirlo en PowerShell).
- PDF sintéticos de alumno y asesor renderizados con `pdftoppm` e
  inspeccionados; los temporales se eliminaron.
- QA visual y de accesibilidad con datos sintéticos: ver
  `docs/checklists/QA_UX_UI.md`.
- `pytest`: 158 aprobadas al cerrar el plan de acceso (177 tras el bloque
  UX/UI) · `ruff check .` sin errores · `compileall` sin
  errores · `git diff --check` sin errores.

## B. Revisión institucional (Orientación y Tutorías)

Sólo la maestra marca estas casillas después de revisar cada contenido.

- [ ] Motivos y acciones sugeridas de `config/alert_rules.csv`.
- [ ] Textos de `config/recommendations.csv`.
- [ ] Recursos y leyenda de `templates/student_report.json`.
- [ ] Áreas del expediente del asesor (`templates/advisor_report.json`).
- [ ] Umbral `minimum_group_size` de `config/parameters.yaml`.
- [ ] Aceptación del recorrido de la interfaz (sección B de
      `docs/checklists/QA_UX_UI.md`).

## C. Autorización

- [ ] La maestra autoriza por escrito procesar las líneas 16 en adelante.

Nombre y firma: ______________________  Fecha: ____________
