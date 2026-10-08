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

- [ ] La aplicación sólo escucha en `127.0.0.1:8501`.
- [ ] Sin contraseña configurada, la aplicación queda bloqueada.
- [ ] Una contraseña incorrecta se rechaza.
- [ ] La contraseña correcta da acceso.
- [ ] **Cerrar sesión** vuelve a pedir la contraseña.
- [ ] Ninguna página consulta la base antes de autenticar.
- [ ] `.streamlit/secrets.toml` está ignorado y no hay contraseña en Git.

### Piloto con las líneas 2–15

- [ ] Se procesaron exactamente 14 registros (líneas 2–15).
- [ ] Mapeo de encabezados válido (105 columnas).
- [ ] Scoring: 126 resultados de área calculados.
- [ ] Alertas y casos calculados sin errores.
- [ ] Recálculo de los 14 envíos sin errores.
- [ ] Umbral de confidencialidad de grupos verificado (pruebas automatizadas).
- [ ] 28 PDF generados y estructuralmente válidos.
- [ ] La base y los PDF temporales se eliminaron al terminar.
- [ ] La salida de consola no contiene datos personales.

### Operación

- [ ] Respaldo de la base probado con una base sintética.
- [ ] Restauración probada con una base sintética.
- [ ] Suite automatizada, Ruff y compilación aprobados.
- [ ] `git ls-files data exports .streamlit/secrets.toml` sólo muestra los
      `.gitkeep`.

## B. Revisión institucional (Orientación y Tutorías)

Sólo la maestra marca estas casillas después de revisar cada contenido.

- [ ] Motivos y acciones sugeridas de `config/alert_rules.csv`.
- [ ] Textos de `config/recommendations.csv`.
- [ ] Recursos y leyenda de `templates/student_report.json`.
- [ ] Áreas del expediente del asesor (`templates/advisor_report.json`).
- [ ] Umbral `minimum_group_size` de `config/parameters.yaml`.
- [ ] Aceptación del recorrido de la interfaz.

## C. Autorización

- [ ] La maestra autoriza por escrito procesar las líneas 16 en adelante.

Nombre y firma: ______________________  Fecha: ____________
