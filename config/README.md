# Configuración del motor

Este directorio contiene las fuentes de verdad versionadas del cuestionario y
del motor de scoring. Python valida y ejecuta estos catálogos; no replica sus
reglas en condicionales.

`questionnaire_draft.csv` contiene únicamente los encabezados extraídos de la
exportación actual. Sus filas no son una fuente de verdad; permanecen en
`pending_review` salvo las variantes históricas verificadas explícitamente.
`questionnaire.csv` sólo puede recibir filas revisadas y aprobadas contra una
fuente institucional.

El catálogo v1.2 vigente contiene 106 columnas aprobadas: 100 preguntas y seis
campos administrativos. No hay filas pendientes de clasificación. Los campos
`ADM_*` se persisten separadamente en estudiantes y envíos; nunca se guardan
como respuestas del cuestionario. `ADM_LAST_MODIFIED_AT` («Last modified
time») es opcional: sólo aparece en la exportación en Excel de Forms y se
descarta al importar.

En la exportación operativa actual, la línea 1 contiene encabezados y todas las
respuestas desde la línea 2 son reales. Administración analiza el archivo
completo antes de solicitar autorización escrita y confirmación para guardarlo.

`questionnaire_aliases.csv` registra variantes históricas autorizadas mediante
coincidencia exacta. Cada alias conserva la versión de origen, el código
canónico, la versión corregida y el motivo. No se permite coincidencia difusa.
Los alias `1.2-xlsx` cubren la exportación en Excel de Forms convertida a CSV:
escribe «ID» en lugar de «Id» y recorta los encabezados largos (CN01, DC01) a
196 caracteres más «...».

`MappingStatus = verified_text` significa que número, `QuestionCode` y texto se
conciliaron con el PDF canónico v1.2, pero aún faltan uno o más campos operativos
como tipo, obligatoriedad o sensibilidad. Estas filas no habilitan importación
ni scoring hasta cambiar a `approved` después de completar su clasificación.

Los códigos `ADM_*` representan metadatos obligatorios de Microsoft Forms. No
participan en scoring. `ADM_RESPONSE_ID`, `ADM_STARTED_AT`, `ADM_COMPLETED_AT`,
`ADM_EMAIL` y `ADM_NAME` se tratan como información personal protegida y deben
persistirse en las entidades administrativas correspondientes, no como
reactivos cuantitativos.

El scoring v0.2 se configura mediante:

- `parameters.yaml`: versión activa, límites de escala y política de áreas
  incompletas.
- `areas.csv`: nueve áreas, umbrales y mínimo de reactivos válidos.
- `area_items.csv`: 64 relaciones área-reactivo y sus pesos.
- `scoring_options.csv`: respuestas exactas, valores corregidos y exclusiones.

Los CSV pueden contener varias versiones. Para cambiar una regla se agregan las
filas de una versión nueva y se cambia `active_scoring_version`; los resultados
históricos conservan la versión con la que fueron calculados. En v0.2 todos los
pesos son `1`, los umbrales por área son `70/40` y `CF05 = No aplica` se excluye
del promedio y del conteo aplicable.

Las alertas se evalúan por separado del scoring mediante:

- `alert_rules.csv`: 44 reglas v0.1 en 24 reactivos. `MatchType = exact`
  compara la respuesta normalizada sin coincidencia difusa; `non_empty` detona
  con cualquier texto abierto no vacío (DC01, DC03) sin copiar el texto a la
  alerta. `RuleVersion` debe coincidir con `active_alert_rules_version`.
- `parameters.yaml`: `alert_levels` define el orden de severidad usado para el
  nivel del caso (`Atención prioritaria > Revisión manual > Seguimiento
  preventivo`); `contact_request_category` marca la fuente
  `Solicitud del alumno`; `minimum_group_size` oculta agregados y datos
  individuales de grupos pequeños; `report_timezone` controla la fecha local
  impresa en los PDFs mediante un identificador IANA.
- `recommendations.csv`: una recomendación por área y semáforo para la versión
  de scoring activa (27 en v0.2), con texto para el alumno y para el personal.
  Un área incompleta no recibe recomendación.
- `sensitive_summary.yaml`: categorías, disparadores, etiquetas y campos
  permitidos para resumir declaraciones `ND`, `SE`, `AP` y `CF`. Esta
  configuración no participa en scoring ni prioridad.
- `report_content.yaml`: introducción, leyenda del semáforo, interpretaciones y
  descripción de las nueve áreas que usan la vista previa y los PDF. Para el
  reporte del alumno también define `student_introduction` y
  `student_labels` (Atender, Dar seguimiento, Fortaleza, Sin información).

El contacto de Orientación del reporte del alumno vive en
`templates/student_report.json` (`"contact"`). Mientras esté vacío, la línea
no se imprime; al llenarlo aparece en el PDF y en la vista previa sin cambiar
código.

Los textos de motivo, acción sugerida y recomendaciones son una primera
redacción operativa y requieren validación de Orientación y Tutorías. Para
cambiarlos sin alterar el historial, crear filas con una versión nueva.

No se deben inferir valores por la posición de una opción ni usar coincidencia
difusa. Una respuesta no configurada deja el área incompleta.
