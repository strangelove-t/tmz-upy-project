# Diseño del esqueleto inicial

## Objetivo

Dejar el repositorio listo para comenzar el desarrollo del MVP descrito en
`docs/Handoff_Tamizaje_UPY_App_Local.md`, sin implementar todavía reglas
de importación, scoring, alertas, persistencia ni reportes.

## Alcance

El esqueleto incluirá:

- Proyecto Python 3.12 con layout `src/` y metadatos en `pyproject.toml`.
- Dependencias de ejecución y desarrollo indicadas en el handoff.
- Aplicación Streamlit local mínima y páginas navegables sin lógica de negocio.
- Paquete `tamizaje` importable con la versión inicial del proyecto y
  `scoring_version = "0.2"` expuesta como constante.
- Estructura completa sugerida por el handoff, incluidos todos los módulos de
  negocio, páginas, catálogos, plantillas, pruebas y directorios operativos.
- Protección mediante `.gitignore` para bases de datos, respuestas exportadas,
  reportes, secretos, entornos virtuales, cachés y logs.
- `.env.example` sin secretos y un lanzador `run_windows.bat` para personal no
  técnico.
- README con instalación, ejecución, pruebas y advertencias de confidencialidad.
- Una prueba de humo en la suite sugerida que valide que el paquete se importa
  y conserva la versión de scoring requerida.

No se crearán reglas ni datos ficticios. Los CSV de `config/` contendrán sólo
sus encabezados contractuales, `parameters.yaml` identificará la versión `0.2`
y un README indicará qué fuentes de verdad deben sustituir o completar esos
archivos antes de implementar el motor.

## Estructura

```text
.
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── app.py
├── run_windows.bat
├── src/
│   └── tamizaje/
│       ├── __init__.py
│       ├── importers.py
│       ├── validation.py
│       ├── normalization.py
│       ├── scoring.py
│       ├── alerts.py
│       ├── cases.py
│       ├── triage.py
│       ├── recommendations.py
│       ├── reports.py
│       ├── database.py
│       └── models.py
├── pages/
│   ├── 1_Resumen.py
│   ├── 2_Casos.py
│   ├── 3_Grupos.py
│   ├── 4_Estudiantes.py
│   └── 5_Reportes.py
├── config/
│   ├── README.md
│   ├── questionnaire.csv
│   ├── areas.csv
│   ├── scoring_options.csv
│   ├── alert_rules.csv
│   ├── recommendations.csv
│   └── parameters.yaml
├── templates/
│   ├── student_report.json
│   └── advisor_report.json
├── tests/
│   ├── fixtures/
│   │   └── synthetic_responses.csv
│   ├── test_import.py
│   ├── test_scoring.py
│   ├── test_alerts.py
│   ├── test_cases.py
│   └── test_reports.py
├── data/.gitkeep
├── exports/.gitkeep
└── references/
    ├── README.md
    ├── Matriz_maestra_scoring_tamizaje_UPY_v0.1.xlsx
    ├── Catalogos_motor_scoring_UPY_v0.1.xlsx
    └── questions.json
```

Los módulos de negocio existirán desde el inicio para reproducir exactamente la
arquitectura acordada, pero sólo contendrán documentación de su responsabilidad.
Los tres archivos de referencia externos se representarán en `references/README.md`
y no se fabricarán binarios o JSON falsos; se incorporarán cuando sean entregados.
Los archivos de pruebas reservados contendrán marcadores de módulo sin pruebas
omitidas o éxitos artificiales; la prueba de humo vivirá en `test_scoring.py`.

## Ejecución local

La instalación recomendada será un entorno virtual local seguido de
`pip install -e ".[dev]"`. La aplicación arrancará con `streamlit run app.py`.
En Windows, `run_windows.bat` comprobará que existe `.venv`, activará el entorno
y ejecutará Streamlit; si falta el entorno, mostrará una instrucción clara y
terminará sin intentar instalar software silenciosamente.

## Interfaz inicial

`app.py` mostrará el nombre del producto, su carácter local, la versión de
scoring y un aviso de que aún no hay datos cargados. Cada página tendrá título,
descripción breve y estado “pendiente de implementación”. No habrá formularios,
persistencia ni datos de demostración.

## Seguridad

El repositorio no contendrá información real. Git ignorará `.env`, bases SQLite,
directorios de importación, archivos de respuestas, PDFs, manifiestos CSV y
logs. Los directorios operativos se conservarán mediante `.gitkeep`. El README
recordará que el repositorio debe permanecer privado y que los datos sólo deben
residir en almacenamiento institucional autorizado.

## Verificación

La validación inicial consistirá en:

1. Ejecutar Pytest para comprobar la importación y la versión `0.2`.
2. Ejecutar Ruff sobre el código y las pruebas.
3. Compilar los módulos Python con `compileall`.
4. Arrancar Streamlit en modo sin interfaz y comprobar que inicia sin errores.

No se crearán commits ni se publicarán cambios al remoto durante este trabajo.
