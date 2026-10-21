# Handoff técnico — Tamizaje y Orientación UPY

> **Documento de alcance inicial conservado como referencia histórica.** Para
> el estado implementado consulta `docs/HANDOFF_2026-10-08.md`. El cambio de
> “asesor” a “tutor”, la síntesis sensible opcional y la importación desde la
> línea 2 ya están implementados.

## 1. Resumen ejecutivo

Se reemplazará el flujo extenso de Power Automate por un motor local y auditable en Python. Microsoft Forms seguirá utilizándose para la captura. Cuando termine el periodo de aplicación, las respuestas se descargarán como CSV o XLSX y se procesarán por lote.

```text
Microsoft Forms
    ↓ exportación CSV/XLSX
Motor Python de procesamiento
    ↓
SQLite + PDFs
    ↓
Aplicación local para Orientación
```

La aplicación estará dirigida a personal no técnico y se abrirá desde un acceso directo. La interfaz se ejecutará localmente con Streamlit; el navegador será únicamente la interfaz y los datos no se publicarán en internet.

### Fecha objetivo

MVP funcional en **cuatro días de desarrollo**.

### Decisiones congeladas para el MVP

- Procesamiento por lote al finalizar la aplicación del Forms.
- Nueve áreas cuantitativas; no se calculará un puntaje global individual.
- `100` significa mayor fortaleza o menor dificultad reportada.
- Semáforo verde: `70–100`.
- Semáforo amarillo: `40–69.99`.
- Semáforo rojo: `<40`.
- Las alertas se calculan por separado del scoring.
- Los textos abiertos requieren revisión humana; no se clasifican automáticamente.
- El instrumento es de tamizaje y orientación, no diagnóstico.
- No se enviarán correos inmediatos a Orientación.
- El MVP genera reportes y un manifiesto de envío; la automatización de correo no debe bloquear la entrega.
- Debido al cambio del umbral verde, la nueva implementación debe identificarse como **`scoring_version = 0.2`**. No sobrescribir silenciosamente resultados calculados con otra versión.

---

## 2. Objetivos funcionales

La herramienta debe permitir:

1. Importar el archivo descargado de Microsoft Forms.
2. Validar columnas, respuestas y duplicados antes de guardar datos.
3. Calcular resultados de las nueve áreas.
4. Asignar semáforos y recomendaciones.
5. Detectar todas las alertas directas.
6. Consolidar un solo caso por envío/alumno.
7. Ordenar casos desde los que requieren atención más pronta.
8. Consultar una vista institucional general.
9. Consultar resultados por carrera y grupo.
10. Consultar el expediente completo de una persona.
11. Registrar estado, contacto, seguimiento y notas del caso.
12. Descargar un expediente sanitizado para asesores.
13. Generar un reporte individual para cada estudiante.
14. Exportar PDFs por lote y un manifiesto `correo → archivo`.

### Fuera del alcance de los primeros cuatro días

- Aplicación publicada en internet.
- Uso simultáneo desde varias computadoras.
- Clasificación automática de textos libres.
- Diagnóstico psicológico o clínico.
- Puntaje global que sustituya los perfiles por área.
- Envío de decenas de notificaciones inmediatas a Orientación.
- Integración obligatoria con Power Automate, SharePoint o Power BI.
- Autenticación institucional compleja mediante Microsoft Graph, salvo que los permisos ya estén disponibles.

---

## 3. Stack recomendado

- **Python 3.12**.
- **Streamlit**: interfaz local.
- **Pandas**: importación y transformación.
- **SQLite** mediante `sqlite3`: persistencia local.
- **Plotly**: gráficas interactivas.
- **ReportLab**: PDFs sin dependencias nativas complejas.
- **Pydantic**: validación de configuraciones y registros.
- **Pytest**: pruebas unitarias y de integración.
- **Ruff**: formato y análisis estático.

Para el MVP, evitar frameworks y servicios adicionales que aumenten el tiempo de instalación.

---

## 4. Estructura sugerida del repositorio

```text
tamizaje-upy/
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
├── data/
│   └── .gitkeep
├── exports/
│   └── .gitkeep
└── references/
    ├── Matriz_maestra_scoring_tamizaje_UPY_v0.1.xlsx
    ├── Catalogos_motor_scoring_UPY_v0.1.xlsx
    └── questions.json
```

### Archivos que nunca deben subirse a GitHub

```gitignore
.env
.venv/
__pycache__/
*.pyc
data/*.db
data/*.sqlite*
data/imports/
exports/**/*.pdf
exports/**/*.csv
responses*.csv
responses*.xlsx
*.log
```

El repositorio debe ser **privado**. No utilizar datos reales en issues, commits, capturas, fixtures ni pull requests.

---

## 5. Fuentes de verdad

Los siguientes catálogos ya existen y deben trasladarse a `config/`:

- `CAT_Areas`.
- `CAT_ScoringOptions`.
- `CAT_AlertRules`.
- `CAT_Recommendations`.
- `CAT_Parameters`.
- Diccionario de preguntas del Forms.

La aplicación no debe contener cientos de reglas dispersas en condicionales. Las reglas se cargan desde archivos de configuración versionados.

### Regla de precedencia

1. `questionnaire.csv` define identidad, número, texto y tipo de cada pregunta.
2. `scoring_options.csv` define los valores corregidos y si una respuesta entra al promedio.
3. `areas.csv` define las áreas y umbrales.
4. `alert_rules.csv` define detonantes, nivel, categoría, motivo y acción sugerida.
5. `recommendations.csv` define recomendaciones por área y semáforo.
6. `parameters.yaml` define políticas generales y versión.

No inferir valores a partir de la posición de una opción. Siempre consultar el catálogo.

---

## 6. Contrato de importación

### Flujo

1. La persona usuaria selecciona el CSV/XLSX exportado de Forms.
2. Se calcula SHA-256 del archivo.
3. Si el hash ya existe en `imports`, se bloquea la importación duplicada.
4. Se normalizan encabezados, Unicode NFC, espacios exteriores y saltos de línea.
5. Los encabezados se vinculan con `QuestionCode` mediante el diccionario.
6. Si falta una columna obligatoria o existe una coincidencia ambigua, el proceso se detiene antes de escribir en la base.
7. Se muestra una previsualización con número de filas válidas, errores, advertencias y posibles duplicados.
8. La persona confirma la importación.
9. El proceso se ejecuta dentro de una transacción SQLite.

### Incidencia operativa del archivo actual

- La línea 1 contiene los encabezados.
- Las líneas 2–15 contienen 14 registros de prueba y se excluyen
  automáticamente de toda importación real.
- La línea 16 en adelante contiene información real, sensible y confidencial.
- El modo seguro analiza sólo las líneas 2–15 y nunca permite persistirlas.
- Los campos `ADM_EMAIL` y `ADM_NAME` se almacenan en `students`;
  `ADM_RESPONSE_ID`, `ADM_STARTED_AT` y `ADM_COMPLETED_AT` se almacenan en
  `submissions`; no se mezclan con `responses`.

### Identificación de envíos

- Usar el identificador de respuesta de Forms cuando esté disponible.
- En su ausencia, generar una clave determinista con correo institucional, fecha de envío y versión del cuestionario.
- Dos archivos con el mismo registro no deben producir resultados o casos duplicados.
- Si una persona tiene dos envíos diferentes, no sobrescribir automáticamente: marcar `duplicate_student_submission = true` para revisión y permitir elegir cuál es vigente.

### Respuestas

- Comparación por coincidencia exacta después de normalizar Unicode y espacios.
- No hacer coincidencia difusa.
- Variantes autorizadas como `Sí`/`Si` deben registrarse explícitamente como alias en configuración.
- Las casillas múltiples deben convertirse a una lista de valores, no conservarse como texto JSON sin interpretar.
- Mantener la respuesta original para auditoría.

---

## 7. Bases del scoring

### Áreas

| Código | Área | Reactivos esperados |
|---|---|---:|
| A01 | Preparación académica | 10 |
| A02 | Hábitos y organización | 10 |
| A03 | Motivación y elección de carrera | 10 |
| A04 | Adaptación e integración | 10 |
| A05 | Recursos económicos | 9 |
| A06 | Contexto familiar y red de apoyo | 6 |
| A07 | Bienestar emocional funcional | 3 |
| A08 | Accesibilidad y funcionamiento físico | 2 |
| A09 | Continuidad y permanencia | 4 |

Total: **64 reactivos cuantitativos**.

Todos tienen peso `1` en la versión 0.2.

### Significado

- `5`: mayor fortaleza o menor dificultad reportada.
- `4`: condición favorable.
- `3`: condición intermedia.
- `2`: dificultad relevante.
- `1`: dificultad marcada.

### Cálculo por área

```python
raw_average = sum(corrected_values) / len(corrected_values)
normalized_score = ((raw_average - 1) / 4) * 100
```

Redondear únicamente para presentación. Conservar precisión completa en base de datos y aplicar los cortes sobre el valor sin redondear.

### Contrato configurable implementado

- `parameters.yaml` selecciona la versión activa y define los límites de escala.
- `areas.csv` define umbrales y mínimo válido por área.
- `area_items.csv` es la única fuente de pertenencia y peso de reactivos.
- `scoring_options.csv` define valores corregidos, alias y exclusiones.
- Los catálogos pueden conservar varias versiones simultáneamente.
- Los resultados se identifican por envío, área y versión; una versión nueva no
  sobrescribe resultados históricos.
- Las respuestas desconocidas o faltantes dejan el área incompleta y nunca
  reciben un valor inferido.
- Una exclusión legítima reduce `ApplicableItemCount`; la completitud exige las
  respuestas aplicables hasta el mínimo configurado.

### Semáforo operativo v0.2

```python
if normalized_score >= 70:
    traffic_light = "Verde"
elif normalized_score >= 40:
    traffic_light = "Amarillo"
else:
    traffic_light = "Rojo"
```

| Intervalo | Semáforo |
|---:|---|
| `70 ≤ score ≤ 100` | Verde |
| `40 ≤ score < 70` | Amarillo |
| `0 ≤ score < 40` | Rojo |

Estos cortes son criterios operativos iniciales, no puntos de corte clínicos.

### Respuestas no aplicables

- Una opción configurada con `IncludeInAverage = false` se excluye del numerador y del denominador.
- Nunca convertir `No aplica` en cero o en uno.
- `ValidItemCount` cuenta solo respuestas puntuables válidas.
- `ApplicableItemCount` cuenta reactivos aplicables después de exclusiones legítimas.
- Si falta una respuesta que sí era aplicable, el área queda `Incompleta`.
- Un área incompleta no recibe semáforo ni recomendación automática hasta su revisión.

### Puntaje global

No calcular un puntaje global individual en el MVP. Mostrar las nueve áreas. Un promedio general podría ocultar un área crítica o una alerta directa.

La **vista general del dashboard** sí puede mostrar agregados institucionales, pero no debe presentarlos como un diagnóstico individual.

---

## 8. Preguntas con puntuación invertida

En estos reactivos, mayor acuerdo o frecuencia representa mayor dificultad; por eso el valor corregido invierte la escala.

### Escalas invertidas

**Frecuencia estándar**

```text
Nunca = 5
Casi nunca = 4
Algunas veces = 3
Casi siempre = 2
Siempre = 1
```

**Acuerdo**

```text
Totalmente en desacuerdo = 5
En desacuerdo = 4
Ni de acuerdo ni en desacuerdo = 3
De acuerdo = 2
Totalmente de acuerdo = 1
```

**PE01 utiliza etiquetas propias**

```text
Nunca = 5
Rara vez = 4
Algunas veces = 3
Frecuentemente = 2
Muy frecuentemente = 1
```

| Código | Núm. Forms | Área | Pregunta |
|---|---:|---|---|
| HO04 | 21 | Hábitos y organización | Suelo dejar las tareas para el último momento. |
| HO05 | 22 | Hábitos y organización | Me cuesta mantener la concentración durante las clases. |
| HO06 | 23 | Hábitos y organización | Me distraigo fácilmente cuando estudio. |
| HO07 | 24 | Hábitos y organización | Tengo dificultades para cumplir con fechas de entrega. |
| HO08 | 25 | Hábitos y organización | Suelo estudiar únicamente cuando tengo un examen. |
| MO08 | 35 | Motivación y elección de carrera | He pensado seriamente en cambiarme de carrera. |
| MO09 | 36 | Motivación y elección de carrera | He pensado en abandonar la universidad. |
| MO10 | 37 | Motivación y elección de carrera | Actualmente tengo dudas importantes sobre si elegí la carrera correcta. |
| ER02 | 49 | Recursos económicos | Tengo dificultades para cubrir mis gastos de transporte hacia la universidad. |
| ER03 | 50 | Recursos económicos | Tengo dificultades para adquirir materiales, libros o herramientas necesarias para mis clases. |
| ER06 | 53 | Recursos económicos | Mi situación económica podría dificultar mi permanencia en la universidad. |
| ER07 | 54 | Recursos económicos | Necesito trabajar para poder continuar estudiando. |
| ER09 | 56 | Recursos económicos | En algún momento he considerado abandonar mis estudios por motivos económicos. |
| FA03 | 59 | Contexto familiar y red de apoyo | Tengo responsabilidades familiares que pueden dificultar mi desempeño académico. |
| FA04 | 60 | Contexto familiar y red de apoyo | Actualmente existe alguna situación familiar que afecta mi concentración o rendimiento. |
| SE04 | 73 | Bienestar emocional funcional | ¿Consideras que actualmente tu bienestar emocional está interfiriendo con tus estudios? |
| SE05 | 74 | Bienestar emocional funcional | Durante las últimas semanas, ¿has tenido dificultades importantes para concentrarte debido a preocupaciones, estrés o estado emocional? |
| SE06 | 75 | Bienestar emocional funcional | Durante las últimas semanas, ¿has tenido dificultades importantes para realizar tus actividades académicas debido a tu estado emocional? |
| PE01 | 91 | Continuidad y permanencia | ¿Con qué frecuencia has pensado que quizá no podrás continuar estudiando en la universidad? |

La implementación debe obtener `CorrectedValue` del catálogo; esta lista sirve para revisión humana, no para duplicar reglas en código.

---

## 9. Reactivos con codificación especial

Estos reactivos no usan una inversión Likert uniforme.

| Código | Núm. Forms | Pregunta | Mapeo corregido |
|---|---:|---|---|
| CF04 | 85 | ¿Esta condición puede dificultar tu asistencia regular a clases? | `No=5`; `Algunas veces=3`; `Sí=1` |
| CF05 | 86 | ¿Esta condición puede dificultar tu participación en actividades prácticas, laboratorios o actividades físicas? | `No=5`; `Algunas veces=3`; `Sí=1`; `No aplica=excluir` |
| PE02 | 92 | ¿Qué tan probable consideras que continúes estudiando en esta universidad durante el próximo cuatrimestre? | `Muy probable=5`; `Probable=4`; `No estoy seguro(a)=3`; `Poco probable=2`; `Nada probable=1` |
| PE04 | 94 | ¿Has considerado cambiarte de carrera? | `No=5`; `Lo he pensado, pero no estoy seguro(a)=3`; `Sí=1` |
| PE05 | 95 | ¿Qué tan seguro(a) estás de haber elegido la carrera adecuada para ti? | `Muy seguro(a)=5`; `Seguro(a)=4`; `Poco seguro(a)=2`; `Nada seguro(a)=1` |

> **Corrección de cuestionario v1.2:** PE02 usa “próximo cuatrimestre”.
> “Próximo semestre” corresponde a versiones anteriores y sólo se admite como
> alias histórico explícito. Véase
> `docs/incidents/2026-10-06-pe02-periodo-academico.md`.

---

## 10. Preguntas que pueden activar alertas

Las alertas se evalúan de forma independiente a los semáforos. Una puntuación verde no neutraliza una respuesta detonante.

Se mantienen tres niveles operativos:

- **Atención prioritaria**.
- **Seguimiento preventivo**.
- **Revisión manual**.

Ninguno equivale por sí mismo a una emergencia clínica. El instrumento actual no incluye un reactivo directo y validado de peligro inmediato, autolesión o ideación suicida.

| Código | Núm. Forms | Tipo | Pregunta | Respuestas detonantes → nivel |
|---|---:|---|---|---|
| MO09 | 36 | Likert frecuencia | He pensado en abandonar la universidad. | `Algunas veces` → **Seguimiento preventivo** (Permanencia)<br>`Casi siempre` → **Atención prioritaria** (Permanencia)<br>`Siempre` → **Atención prioritaria** (Permanencia) |
| ER06 | 53 | Likert acuerdo | Mi situación económica podría dificultar mi permanencia en la universidad. | `Totalmente de acuerdo` → **Seguimiento preventivo** (Económica) |
| ER09 | 56 | Likert acuerdo | En algún momento he considerado abandonar mis estudios por motivos económicos. | `De acuerdo` → **Seguimiento preventivo** (Económica)<br>`Totalmente de acuerdo` → **Atención prioritaria** (Económica) |
| ND04 | 66 | Likert frecuencia | ¿Esta condición representa actualmente alguna dificultad para tu desempeño académico? | `Casi siempre` → **Atención prioritaria** (Apoyo educativo)<br>`Siempre` → **Atención prioritaria** (Apoyo educativo) |
| ND06 | 68 | Opción única | ¿Consideras que actualmente necesitas algún apoyo específico de la universidad relacionado con esta condición? | `Sí` → **Seguimiento preventivo** (Apoyo educativo)<br>`No estoy seguro(a)` → **Seguimiento preventivo** (Apoyo educativo) |
| SE04 | 73 | Likert frecuencia | ¿Consideras que actualmente tu bienestar emocional está interfiriendo con tus estudios? | `Algunas veces` → **Seguimiento preventivo** (Bienestar emocional)<br>`Casi siempre` → **Atención prioritaria** (Bienestar emocional)<br>`Siempre` → **Atención prioritaria** (Bienestar emocional) |
| SE05 | 74 | Likert frecuencia | Durante las últimas semanas, ¿has tenido dificultades importantes para concentrarte debido a preocupaciones, estrés o estado emocional? | `Casi siempre` → **Atención prioritaria** (Bienestar emocional)<br>`Siempre` → **Atención prioritaria** (Bienestar emocional) |
| SE06 | 75 | Likert frecuencia | Durante las últimas semanas, ¿has tenido dificultades importantes para realizar tus actividades académicas debido a tu estado emocional? | `Casi siempre` → **Atención prioritaria** (Bienestar emocional)<br>`Siempre` → **Atención prioritaria** (Bienestar emocional) |
| SE07 | 76 | Opción única | ¿Has interrumpido anteriormente tus estudios debido a una situación emocional o psicológica? | `Sí` → **Seguimiento preventivo** (Bienestar emocional) |
| SE08 | 77 | Opción única | ¿Consideras que necesitas actualmente apoyo psicológico u orientación dentro de la universidad? | `Sí` → **Atención prioritaria** (Bienestar emocional) |
| AP03 | 80 | Opción única | ¿Actualmente esta situación requiere algún tipo de apoyo o seguimiento para facilitar tu permanencia y desempeño universitario? | `Sí` → **Atención prioritaria** (Apoyo personal)<br>`No estoy seguro(a)` → **Seguimiento preventivo** (Apoyo personal) |
| AP04 | 81 | Opción única | ¿Existe alguna recomendación profesional previa que consideres importante que la universidad conozca para brindarte apoyo académico? | `Sí` → **Seguimiento preventivo** (Apoyo personal)<br>`Prefiero hablarlo personalmente con Orientación y Tutorías` → **Atención prioritaria** (Apoyo personal) |
| CF04 | 85 | Opción única | ¿Esta condición puede dificultar tu asistencia regular a clases? | `Sí` → **Atención prioritaria** (Accesibilidad)<br>`Algunas veces` → **Seguimiento preventivo** (Accesibilidad) |
| CF05 | 86 | Opción única | ¿Esta condición puede dificultar tu participación en actividades prácticas, laboratorios o actividades físicas? | `Sí` → **Atención prioritaria** (Accesibilidad)<br>`Algunas veces` → **Seguimiento preventivo** (Accesibilidad) |
| CF06 | 87 | Opción única | ¿Utilizas actualmente algún apoyo o dispositivo para realizar tus actividades cotidianas o académicas? | `Prefiero agendar una cita para platicarlo en orientación` → **Atención prioritaria** (Accesibilidad) |
| CF08 | 89 | Opción única | ¿Requieres alguna adecuación o apoyo específico dentro de la universidad debido a una condición física, sensorial o de salud? | `Sí` → **Atención prioritaria** (Accesibilidad)<br>`No estoy seguro(a)` → **Seguimiento preventivo** (Accesibilidad) |
| CF09 | 90 | Opción única | ¿Existe alguna recomendación médica o profesional que sea importante considerar durante tu estancia en la universidad? | `Sí` → **Seguimiento preventivo** (Accesibilidad)<br>`Prefiero agendar una cita directamente con Orientación y Tutorías` → **Atención prioritaria** (Accesibilidad) |
| PE01 | 91 | Likert frecuencia | ¿Con qué frecuencia has pensado que quizá no podrás continuar estudiando en la universidad? | `Algunas veces` → **Seguimiento preventivo** (Permanencia)<br>`Frecuentemente` → **Atención prioritaria** (Permanencia)<br>`Muy frecuentemente` → **Atención prioritaria** (Permanencia) |
| PE02 | 92 | Opción ordinal | ¿Qué tan probable consideras que continúes estudiando en esta universidad durante el próximo cuatrimestre? | `No estoy seguro(a)` → **Seguimiento preventivo** (Permanencia)<br>`Poco probable` → **Atención prioritaria** (Permanencia)<br>`Nada probable` → **Atención prioritaria** (Permanencia) |
| PE04 | 94 | Opción única | ¿Has considerado cambiarte de carrera? | `Sí` → **Seguimiento preventivo** (Orientación vocacional)<br>`Lo he pensado, pero no estoy seguro(a)` → **Seguimiento preventivo** (Orientación vocacional) |
| PE06 | 96 | Opción única | ¿Consideras que actualmente necesitas algún tipo de apoyo académico para continuar exitosamente tus estudios? | `Sí` → **Seguimiento preventivo** (Apoyo académico) |
| DC01 | 98 | Texto abierto | ¿Existe alguna situación personal, familiar, económica, académica o de cualquier otra índole que consideres importante que la universidad conozca porque pudiera dificultar tu permanencia o desempeño académico? | `Cualquier texto no vacío` → **Revisión manual** (Situación declarada) |
| DC02 | 99 | Opción única | ¿Te gustaría que un integrante del Área de Orientación y Tutorías se pusiera en contacto contigo para conversar sobre alguna situación que actualmente te preocupa? | `Sí` → **Atención prioritaria** (Solicitud de contacto) |
| DC03 | 100 | Texto abierto | Si deseas, describe brevemente la situación o el tipo de apoyo que consideras necesario. | `Cualquier texto no vacío` → **Revisión manual** (Solicitud abierta) |

El catálogo contiene **44 reglas** distribuidas en estos 24 reactivos. Cada coincidencia produce una alerta independiente y conserva `RuleCode`, respuesta detonante, categoría, nivel, motivo, acción sugerida y versión.

---

## 11. Consolidación de casos

### Regla

- Cero alertas: no se crea caso automático.
- Una o más alertas: se crea un solo caso por envío.
- Todas las alertas permanecen vinculadas al caso.
- No crear un caso por cada alerta.

### Nivel del caso

El nivel se obtiene de la alerta de mayor severidad:

```text
Atención prioritaria > Revisión manual > Seguimiento preventivo
```

`Revisión manual` no significa menor importancia clínica; indica que un texto debe leerse antes de clasificarlo. La interfaz debe destacarlo claramente.

### Fuente del caso

- Si `DC02 = Sí`: `Solicitud del alumno`.
- En caso contrario, si hay alertas: `Alerta automática`.
- Un texto abierto puede añadir `Revisión manual`, pero no debe ser interpretado por palabras clave en el MVP.

### Orden de atención predeterminado

Usar orden lexicográfico y explicable, no una fórmula clínica opaca:

1. Solicitud explícita de contacto.
2. Severidad del caso.
3. Menor puntuación completa entre sus nueve áreas, ascendente.
4. Número de alertas de atención prioritaria, descendente.
5. Número total de alertas, descendente.
6. Fecha de detección, ascendente.

Guardar los componentes por separado:

```text
case_level_rank
requested_contact
lowest_area_score
priority_alert_count
total_alert_count
detected_at
```

La UI permitirá ordenar directamente por cualquier columna, especialmente por número de alertas.

---

## 12. Modelo mínimo de datos

### `imports`

- `id`
- `filename`
- `sha256`
- `imported_at`
- `questionnaire_version`
- `scoring_version`
- `row_count`
- `status`

### `students`

- `id`
- `student_upn`
- `student_name`
- `career`
- `group_name`
- datos generales estrictamente necesarios

### `submissions`

- `id`
- `external_response_id`
- `student_id`
- `submitted_at`
- `import_id`
- `is_current`
- `duplicate_student_submission`

### `responses`

- `submission_id`
- `question_code`
- `response_raw`
- `response_normalized`
- `is_sensitive`

### `area_results`

- `submission_id`
- `area_code`
- `raw_average`
- `normalized_score`
- `traffic_light`
- `valid_item_count`
- `applicable_item_count`
- `expected_item_count`
- `is_complete`
- `recommendation_code`
- `scoring_version`
- `calculation_notes`

### `alerts`

- `id`
- `submission_id`
- `rule_code`
- `question_code`
- `trigger_response`
- `alert_level`
- `alert_category`
- `alert_reason`
- `suggested_action`
- `detected_at`
- `rule_version`

### `cases`

- `id`
- `submission_id`
- `case_level`
- `case_source`
- `case_status`
- `opened_at`
- `assigned_to`
- `initial_reason`
- `contact_status`
- `first_contact_at`
- `last_contact_at`
- `next_follow_up_at`
- `referral_destination`
- `closed_at`
- `closure_reason`
- `resolution_notes`
- `lowest_area_score`
- `critical_area_code`
- `priority_alert_count`
- `total_alert_count`

### `case_notes`

- `id`
- `case_id`
- `created_at`
- `author`
- `note`

### `exports`

- `id`
- `submission_id`
- `export_type`
- `generated_at`
- `file_path`
- `template_version`

---

## 13. Interfaz local

### Resumen

- Alumnos procesados.
- Casos nuevos y pendientes.
- Casos por nivel.
- Solicitudes explícitas de contacto.
- Distribución por área y semáforo.
- Áreas con menor promedio por grupo.
- Fecha y versión de la última importación.

### Casos

- Tabla ordenada por prioridad.
- Filtros por carrera, grupo, nivel, categoría, estado y responsable.
- Búsqueda por nombre, matrícula o correo institucional.
- Acciones para contactar, programar seguimiento, canalizar y cerrar.
- Mostrar por qué aparece primero un caso.

### Grupos

- Selector de carrera y grupo.
- Cantidad de alumnos evaluados.
- Promedio y distribución de semáforos por área.
- Casos por nivel.
- Lista de estudiantes priorizada.
- No mostrar agregados sensibles de subgrupos demasiado pequeños.

### Estudiante

- Datos administrativos.
- Nueve resultados de área.
- Gráfica y semáforo por área.
- Recomendaciones para alumno y personal.
- Alertas detonadas.
- Respuestas sensibles en sección separada.
- Caso y seguimiento.
- Botones de reporte.

### Reportes

- Generar reporte individual del alumno.
- Generar expediente sanitizado para asesor.
- Generar todos los reportes por lote.
- Descargar manifiesto de envío.

---

## 14. Reportes y confidencialidad

### Reporte del estudiante

Puede incluir:

- Identificación básica.
- Resultado de cada área completa.
- Fortalezas y áreas de oportunidad.
- Recomendaciones para el alumno.
- Recursos institucionales.
- Leyenda de que no es un diagnóstico.

No incluir:

- Nivel interno de atención.
- Reglas o códigos de alerta.
- Notas del personal.
- Respuestas de salud o diagnósticos.
- Texto abierto confidencial.

### Expediente para asesor

Aplicar **lista blanca**, no eliminación posterior. Solo se renderizan campos previamente autorizados:

- Nombre y matrícula si son necesarios para la atención.
- Carrera y grupo.
- Áreas académicas relevantes.
- Semáforos y recomendaciones académicas.
- Acciones sugeridas para el asesor.
- Fecha y versión.

Excluir:

- UPN/correo si no es necesario.
- Diagnósticos psicológicos, psiquiátricos, físicos o de neurodesarrollo.
- Respuestas abiertas.
- Alertas internas.
- Notas de Orientación.
- Historial médico o de atención.

La aplicación debe mostrar una vista previa antes de descargar el expediente.

---

## 15. Seguridad y operación

- Usar una computadora institucional con cuenta individual.
- Activar cifrado de disco, idealmente BitLocker.
- No guardar información real dentro del repositorio.
- No sincronizar la base a cuentas personales.
- Respaldar la base en almacenamiento institucional autorizado y cifrado.
- Mantener la exportación original en una ubicación restringida.
- Registrar importaciones y generación de reportes.
- No registrar respuestas sensibles en logs de depuración.
- Cerrar la aplicación antes de copiar o respaldar SQLite.
- La aplicación local será inicialmente de un solo usuario.

---

## 16. Pruebas mínimas de aceptación

### Scoring

- Promedio `5.00` produce `100` y verde.
- Promedio `3.80` produce `70` y verde.
- Un resultado menor a `70` y mayor o igual a `40` produce amarillo.
- Un resultado menor a `40` produce rojo.
- `No aplica` se excluye del denominador.
- Una respuesta faltante aplicable produce área incompleta.
- Los 19 reactivos invertidos usan el valor corregido.
- Los 5 reactivos especiales respetan su tabla exacta.

### Alertas

- `MO09 = Siempre` crea atención prioritaria.
- `SE04 = Algunas veces` crea seguimiento preventivo.
- `DC02 = Sí` crea atención prioritaria y fuente `Solicitud del alumno`.
- Texto no vacío en `DC01` o `DC03` crea revisión manual sin clasificación automática.
- Una respuesta no configurada no genera alerta.
- Varias reglas producen varias alertas, pero un solo caso.

### Duplicados y auditoría

- Reimportar el mismo archivo no duplica registros.
- Reimportar el mismo envío en otro archivo no duplica casos.
- Una segunda respuesta del mismo alumno se marca para revisión.
- Cada resultado conserva versiones de cuestionario, scoring y reglas.

### Reportes

- El reporte del estudiante no contiene alertas internas.
- El expediente del asesor no contiene respuestas sensibles ni texto abierto.
- Los PDFs se pueden abrir y los nombres de archivo son deterministas.

---

## 17. Plan de trabajo de cuatro días

### Día 1 — Configuración, importación y scoring

- Crear repositorio privado y estructura.
- Exportar catálogos a CSV.
- Implementar diccionario de preguntas y mapeo de columnas.
- Implementar validación de importación.
- Implementar valores directos, invertidos y especiales.
- Implementar áreas, completitud, normalización y semáforos v0.2.
- Añadir pruebas de scoring.

### Día 2 — Alertas, casos y persistencia

- Crear esquema SQLite.
- Implementar las 44 reglas de alerta desde catálogo.
- Consolidar casos.
- Implementar orden de atención.
- Resolver duplicados e idempotencia.
- Añadir pruebas de alertas y casos.

### Día 3 — Interfaz

- Resumen general.
- Vista de casos.
- Vista por grupo.
- Expediente individual.
- Filtros y búsqueda.
- Actualización de estados, contacto y notas.

### Día 4 — PDFs, empaquetado y validación

- Reporte del estudiante.
- Expediente sanitizado para asesor.
- Exportación por lote y manifiesto.
- Prueba completa con copia anonimizada del archivo real.
- `run_windows.bat` y guía breve.
- Corrección de errores críticos y entrega.

---

## 18. División sugerida entre dos desarrolladores

### Desarrollador A — Motor

- Configuraciones.
- Importación y normalización.
- Scoring.
- Alertas.
- Casos y triage.
- Pruebas del dominio.

### Desarrollador B — Aplicación

- Base de datos y repositorios de consulta.
- Pantallas Streamlit.
- Gráficas y filtros.
- PDFs y plantillas.
- Launcher y documentación de usuario.

### Contrato común desde el primer día

Definir dataclasses/Pydantic models compartidos para:

```text
NormalizedSubmission
ScoredArea
TriggeredAlert
ConsolidatedCase
StudentReportData
AdvisorReportData
```

No esperar hasta el día 3 para integrar. Hacer una integración al final de cada día.

### Flujo Git simple

- Rama protegida `main`.
- Ramas cortas `feature/import-scoring`, `feature/alerts-cases`, `feature/dashboard`, `feature/reports`.
- Pull requests pequeños con al menos una revisión.
- No subir datos reales.
- Cada cambio de regla debe modificar configuración, prueba y versión cuando corresponda.

---

## 19. Definición de terminado del MVP

El MVP se considera listo cuando:

- Un archivo de Forms válido puede importarse sin editar código.
- Los 64 reactivos cuantitativos se procesan desde catálogo.
- Los semáforos usan verde `≥70`.
- Las 44 reglas de alerta se evalúan correctamente.
- Se genera máximo un caso por envío.
- Los casos se pueden ordenar y filtrar.
- Existen vistas general, grupal e individual.
- Se puede actualizar el seguimiento de un caso.
- Se generan ambos tipos de PDF.
- El expediente para asesor no expone información confidencial.
- La herramienta puede abrirse mediante un acceso directo en la computadora institucional.
- Las pruebas automatizadas pasan con datos sintéticos.

---

## 20. Advertencia metodológica

La matriz actual es un modelo operativo de tamizaje y todavía requiere validación formal por Orientación. No cuenta con validación psicométrica ni puntos de corte clínicos. Los semáforos, alertas y el orden de atención ayudan a organizar el trabajo institucional; no diagnostican, no determinan por sí solos una intervención clínica y no deben utilizarse para excluir estudiantes.
