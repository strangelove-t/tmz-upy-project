# Diccionario del cuestionario Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir los 105 encabezados del CSV actual en un diccionario de cuestionario revisable y validar futuras exportaciones mediante coincidencia exacta, sin leer ni exponer respuestas reales.

**Architecture:** Un módulo de catálogo carga definiciones aprobadas y compara encabezados normalizados. Una herramienta separada genera un borrador exclusivamente desde la primera línea del CSV; el borrador nunca se considera fuente de verdad hasta pasar revisión humana y publicarse como `config/questionnaire.csv`.

**Tech Stack:** Python 3.12, biblioteca estándar (`csv`, `dataclasses`, `pathlib`), Pydantic, Streamlit, Pytest y Ruff.

---

## Estado de ejecución

- Tasks 1 a 5: completadas.
- Task 3: las 100 preguntas y los cinco campos administrativos están
  clasificados y en estado `approved`. El catálogo tiene 105 de 105 columnas
  aprobadas, sin pendientes.
- Task 6: la validación del catálogo está completa. La importación real sigue
  bloqueada deliberadamente hasta persistir los campos `ADM_*` en entidades
  administrativas especializadas, en lugar de guardarlos como respuestas.

---

## Condiciones previas y reglas de seguridad

- Leer únicamente la línea de encabezados del archivo actual.
- No abrir, imprimir, copiar ni resumir las líneas 16 en adelante.
- No inferir `QuestionCode` por posición, similitud difusa o contenido de respuestas.
- Permitir asignación automática sólo por coincidencia exacta normalizada con una
  fuente ya aprobada.
- Mantener separados el borrador de trabajo y el catálogo aprobado.
- No importar datos reales mientras existan encabezados obligatorios sin mapear o
  coincidencias ambiguas.

## Archivos previstos

- Create: `src/tamizaje/questionnaire.py`
- Create: `src/tamizaje/questionnaire_draft.py`
- Modify: `src/tamizaje/validation.py`
- Modify: `src/tamizaje/importers.py`
- Modify: `app.py`
- Modify: `config/questionnaire.csv`
- Create: `config/questionnaire_draft.csv`
- Modify: `config/README.md`
- Create: `tests/test_questionnaire.py`
- Modify: `tests/test_import.py`

---

### Task 1: Definir el contrato del cuestionario

**Files:**
- Create: `src/tamizaje/questionnaire.py`
- Create: `tests/test_questionnaire.py`

- [ ] **Step 1: Escribir pruebas fallidas del modelo**

Probar un modelo `QuestionDefinition` con estos campos obligatorios:

```python
QuestionDefinition(
    question_code="MO09",
    forms_number=36,
    question_text="He pensado en abandonar la universidad.",
    question_type="likert_frequency",
    required=True,
    is_sensitive=False,
    questionnaire_version="0.1",
    mapping_status="approved",
)
```

Las pruebas deben rechazar código vacío, número menor que uno, estados fuera de
`pending_review|approved` y filas aprobadas sin código.

- [ ] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_questionnaire.py -v`
Expected: FAIL porque el módulo no existe.

- [ ] **Step 3: Implementar el modelo mínimo**

Crear `QuestionDefinition` con Pydantic y constantes cerradas para tipos y
estados. No añadir categorías no observadas o no aprobadas.

- [ ] **Step 4: Implementar carga estricta**

Crear:

```python
def load_questionnaire(path: Path) -> tuple[QuestionDefinition, ...]: ...
```

Debe validar encabezados del catálogo, códigos únicos, números únicos y textos
normalizados únicos. Los errores deben referirse a la fila del catálogo, no a
respuestas del alumnado.

- [ ] **Step 5: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_questionnaire.py -v`
Expected: todas las pruebas del contrato pasan.

### Task 2: Extraer un borrador sólo desde encabezados

**Files:**
- Create: `src/tamizaje/questionnaire_draft.py`
- Create: `config/questionnaire_draft.csv`
- Modify: `tests/test_questionnaire.py`

- [ ] **Step 1: Escribir pruebas fallidas de extracción**

Probar que `build_questionnaire_draft`:

- acepta bytes CSV y reutiliza la detección segura de codificación/separador;
- lee únicamente el primer registro CSV;
- crea una fila por encabezado en el mismo orden;
- asigna `mapping_status=pending_review`;
- deja vacíos `QuestionCode`, `QuestionType`, `Required` e `IsSensitive`;
- no incluye respuestas en el objeto, CSV generado o `repr`.

- [ ] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_questionnaire.py -v`
Expected: FAIL por función inexistente.

- [ ] **Step 3: Implementar extracción y exportación**

Crear:

```python
def build_questionnaire_draft(filename: str, content: bytes) -> QuestionnaireDraft: ...
def write_questionnaire_draft(draft: QuestionnaireDraft, path: Path) -> None: ...
```

El borrador incluirá `SourceColumnIndex`, `SourceHeader`, `NormalizedHeader`,
`QuestionCode`, `FormsNumber`, `QuestionType`, `Required`, `IsSensitive`,
`QuestionnaireVersion`, `MappingStatus` y `ReviewNotes`.

- [ ] **Step 4: Generar el borrador del archivo actual**

Ejecutar la herramienta sobre el CSV ignorado en `data/`. La salida permitida en
consola será únicamente:

```text
105 encabezados extraídos; 105 pendientes de revisión; 0 respuestas leídas.
```

- [ ] **Step 5: Verificar el borrador**

Comprobar 105 filas, índices únicos de 1 a 105, encabezados normalizados únicos y
ausencia de valores de respuestas. No publicar todavía como catálogo aprobado.

### Task 3: Revisión humana y publicación del catálogo

**Files:**
- Modify: `config/questionnaire_draft.csv`
- Modify: `config/questionnaire.csv`
- Modify: `config/README.md`

- [ ] **Step 1: Clasificar columnas administrativas**

Revisar manualmente los encabezados de identificación, fecha, carrera, grupo y
metadatos de Forms. Asignar códigos administrativos documentados con prefijo
`ADM_`, tipo, obligatoriedad y sensibilidad. No copiar ejemplos de valores.

- [ ] **Step 2: Vincular preguntas conocidas**

Usar únicamente coincidencia exacta normalizada contra textos y códigos ya
documentados en el handoff o entregados en una fuente institucional. Registrar
en `ReviewNotes` la fuente utilizada para cada asignación.

- [ ] **Step 3: Dejar explícitos los huecos**

Las preguntas sin fuente confiable permanecen `pending_review`, con código y
tipo vacíos. No usar códigos provisionales que parezcan definitivos.

- [ ] **Step 4: Ejecutar revisión de cuatro ojos**

Una segunda persona autorizada verifica texto, código, número de Forms, tipo,
obligatoriedad y sensibilidad. Sólo entonces cambia `MappingStatus` a
`approved`.

- [ ] **Step 5: Publicar el catálogo aprobado**

Copiar a `config/questionnaire.csv` únicamente filas aprobadas. Mantener el
borrador completo para seguimiento y documentar conteos de aprobadas y
pendientes, sin incluir datos de respuestas.

**Checkpoint obligatorio:** Si falta `questions.json` u otra fuente oficial, el
trabajo puede cerrar con un borrador parcial, pero no puede declarar completo el
mapeo ni habilitar scoring.

### Task 4: Comparar exportaciones contra el catálogo

**Files:**
- Modify: `src/tamizaje/questionnaire.py`
- Modify: `src/tamizaje/validation.py`
- Modify: `src/tamizaje/importers.py`
- Modify: `tests/test_questionnaire.py`
- Modify: `tests/test_import.py`

- [ ] **Step 1: Escribir pruebas fallidas de comparación**

Cubrir coincidencia exacta normalizada, columna obligatoria faltante, columna
desconocida, texto duplicado en catálogo y coincidencia ambigua. Probar que los
mensajes sólo muestran códigos o índices, no respuestas.

- [ ] **Step 2: Implementar comparación**

Crear:

```python
def compare_headers(
    headers: tuple[str, ...],
    questionnaire: tuple[QuestionDefinition, ...],
) -> HeaderMappingResult: ...
```

El resultado contendrá asignaciones por índice, códigos faltantes, índices
desconocidos, errores y advertencias. No habrá coincidencia difusa.

- [ ] **Step 3: Integrar con `CsvPreview`**

Permitir que `preview_csv` reciba opcionalmente el catálogo aprobado y adjunte
el resultado del mapeo. Un error de mapeo bloquea persistencia.

- [ ] **Step 4: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_questionnaire.py tests/test_import.py -v`
Expected: todas las pruebas pasan.

### Task 5: Mostrar cobertura del mapeo en Streamlit

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Escribir prueba de interfaz fallida**

Comprobar que la aplicación muestra conteos de columnas aprobadas, pendientes,
desconocidas y ambiguas, sin renderizar textos de respuestas.

- [ ] **Step 2: Implementar resumen seguro**

Mostrar únicamente conteos y códigos aprobados. Para columnas pendientes, usar
índice de columna; no mostrar respuestas. Deshabilitar `Confirmar importación`
cuando falte cualquier columna obligatoria o exista ambigüedad.

- [ ] **Step 3: Verificar interfaz**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`
Expected: pruebas de interfaz pasan.

### Task 6: Verificación y entrega

- [ ] **Step 1: Ejecutar suite completa**

Run: `.venv/bin/python -m pytest -v`
Expected: cero fallos y cero pruebas omitidas.

- [ ] **Step 2: Ejecutar análisis estático y compilación**

Run: `.venv/bin/python -m ruff check .`
Expected: `All checks passed!`.

Run: `.venv/bin/python -m compileall -q app.py pages src tests`
Expected: exit code 0.

- [ ] **Step 3: Validar seguridad**

Confirmar que el CSV original, SQLite y cualquier exportación con respuestas
permanecen ignorados por Git. Revisar el diff para comprobar que sólo se
versionaron encabezados, metadatos y pruebas sintéticas.

- [ ] **Step 4: Criterio de salida**

Entregar una matriz de cobertura con: total de columnas, aprobadas, pendientes,
desconocidas y ambiguas. Scoring sólo puede comenzar cuando estén aprobados los
64 reactivos cuantitativos y existan sus opciones oficiales; las alertas sólo
cuando estén aprobados sus 24 reactivos y las 44 reglas.

No crear commit ni publicar al remoto sin autorización explícita.
