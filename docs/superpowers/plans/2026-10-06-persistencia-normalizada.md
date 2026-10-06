# Persistencia normalizada de importaciones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importar únicamente registros reales y guardar identidad, envíos y respuestas en entidades SQLite separadas y auditables.

**Architecture:** `preview_csv` seleccionará filas sin perder su número original. `import_preview` resolverá cada columna mediante el catálogo aprobado, extraerá campos especializados y realizará una única transacción que crea o reutiliza estudiantes, crea envíos y guarda sólo respuestas no administrativas.

**Tech Stack:** Python 3.12, biblioteca estándar (`csv`, `sqlite3`, `dataclasses`), Pydantic, Streamlit, Pytest y Ruff.

---

## Reglas de ejecución

- No leer, imprimir ni incluir en fixtures respuestas reales.
- Usar solamente CSV sintéticos en pruebas.
- No crear commits, conforme a la preferencia vigente del proyecto.
- Ejecutar cada tarea con ciclo RED–GREEN antes de continuar.

### Task 1: Seleccionar filas reales conservando auditoría

**Files:**
- Modify: `src/tamizaje/importers.py`
- Modify: `tests/test_import.py`

- [x] **Step 1: Escribir la prueba fallida de exclusión**

Añadir una prueba sintética que construya 16 filas numeradas y ejecute:

```python
preview = preview_csv("synthetic.csv", content, skip_rows=14)

assert preview.row_count == 2
assert preview.source_row_numbers == (16, 17)
assert not preview.is_limited
```

- [x] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py::test_preview_skips_test_rows_and_preserves_source_lines -v`

Expected: FAIL porque `preview_csv` no acepta `skip_rows`.

- [x] **Step 3: Implementar selección mínima**

Agregar `skip_rows: int = 0`, rechazar valores negativos y omitir esa cantidad
de filas después del encabezado. Añadir a `CsvPreview`:

```python
source_row_numbers: tuple[int, ...]
```

Calcular cada línea como `2 + skip_rows + row_offset`. `is_limited` debe depender
sólo de `max_rows`, no de `skip_rows`.

- [x] **Step 4: Probar interacción con modo seguro**

Añadir una prueba que use `max_rows=14` sin `skip_rows` y confirme números
`2..15` y `is_limited is True`.

- [x] **Step 5: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`

Expected: todas las pruebas de importación pasan.

### Task 2: Reemplazar el esquema provisional

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `tests/test_import.py`

- [x] **Step 1: Escribir la prueba fallida del esquema**

Después de `initialize_database`, consultar `PRAGMA table_info` y comprobar los
campos definidos en la especificación:

```python
assert {"student_upn", "student_upn_normalized", "student_name", "career", "group_name"} <= student_columns
assert {"external_response_id", "student_id", "source_row_number", "started_at", "submitted_at", "is_current", "duplicate_student_submission"} <= submission_columns
assert {"question_code", "response_raw", "response_normalized", "is_sensitive"} <= response_columns
```

- [x] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py::test_database_initializes_normalized_schema -v`

Expected: FAIL porque no existe `students` y las otras tablas conservan el
contrato provisional.

- [x] **Step 3: Implementar el esquema mínimo**

Crear `students` con unicidad en `student_upn_normalized`; ampliar `imports` con
`questionnaire_version` y `scoring_version`; reemplazar `submissions` y
`responses` según la especificación. Establecer `UNIQUE(external_response_id)` y
`PRIMARY KEY(submission_id, question_code)`.

No implementar migraciones: no existe una base del proyecto que conservar.

- [x] **Step 4: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py::test_database_initializes_normalized_schema -v`

Expected: PASS.

### Task 3: Persistir un envío separado por entidades

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `tests/test_import.py`

- [x] **Step 1: Crear un catálogo y CSV sintéticos completos**

La prueba debe incluir los siete códigos especializados y dos reactivos:

```text
ADM_RESPONSE_ID, ADM_STARTED_AT, ADM_COMPLETED_AT, ADM_EMAIL, ADM_NAME,
DG02, DG03, Q01, Q02
```

Los valores serán ficticios y no reutilizarán ningún dato del archivo real.

- [x] **Step 2: Escribir la prueba fallida de separación**

Importar una fila y comprobar:

```python
assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
assert connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 2
```

Verificar además que correo, nombre, carrera y grupo están en `students`; que
identificador y fechas están en `submissions`; y que `responses` contiene sólo
`Q01` y `Q02` con su marca de sensibilidad.

- [x] **Step 3: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py::test_database_separates_student_submission_and_responses -v`

Expected: FAIL porque el backend aún bloquea todos los códigos `ADM_*`.

- [x] **Step 4: Implementar extracción por código**

Construir índices `QuestionCode → índice de columna` desde
`preview.mapping.assignments` y definiciones `QuestionCode → QuestionDefinition`
desde el catálogo. Cambiar la firma a:

```python
def import_preview(
    connection: sqlite3.Connection,
    preview: CsvPreview,
    questionnaire: tuple[QuestionDefinition, ...],
) -> int:
```

Validar que los siete campos especializados existan y no estén vacíos. Insertar
o recuperar al estudiante mediante el correo normalizado con `casefold()`;
insertar el envío; insertar con `executemany` únicamente códigos no
especializados. Usar `preview.source_row_numbers`.

- [x] **Step 5: Conservar atomicidad y errores seguros**

Actualizar las pruebas de preview inválida, hash repetido y rollback para pasar
el catálogo. Agregar una prueba de campo administrativo vacío que espere
`InvalidPreviewError` y compruebe cero filas en todas las tablas.

- [x] **Step 6: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`

Expected: todas las pruebas pasan.

### Task 4: Manejar múltiples envíos sin sobrescribir

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `tests/test_import.py`

- [x] **Step 1: Escribir la prueba fallida de segundo envío**

Importar dos previews sintéticos con hashes e identificadores externos distintos,
pero el mismo correo con diferencias de mayúsculas. Comprobar:

```python
assert student_count == 1
assert submissions == [(1, 0), (0, 1)]
```

La tupla representa `(is_current, duplicate_student_submission)` ordenada por
`id`. Confirmar que nombre, carrera y grupo originales no fueron reemplazados.

- [x] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py::test_second_submission_reuses_student_and_requires_review -v`

Expected: FAIL hasta implementar la detección de envíos previos.

- [x] **Step 3: Implementar la regla mínima**

Antes de crear el envío, consultar si el estudiante tiene otro. Para el primero
usar `is_current=1` y `duplicate_student_submission=0`; para posteriores usar
`is_current=0` y `duplicate_student_submission=1`. No actualizar el registro de
`students` existente.

- [x] **Step 4: Probar identificador externo duplicado**

Importar otro archivo sintético con `ADM_RESPONSE_ID` ya existente y esperar
`DuplicateImportError`; comprobar rollback completo del segundo archivo.

- [x] **Step 5: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`

Expected: todas las pruebas pasan.

### Task 5: Habilitar la importación real controlada

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`
- Modify: `config/README.md`
- Modify: `docs/Handoff_Tamizaje_UPY_App_Local.md`

- [x] **Step 1: Escribir la prueba fallida de configuración de filas**

Extraer una función pura o constante verificable para que el modo real use
`skip_rows=14` y el modo seguro use `max_rows=14`. La prueba debe confirmar que
la UI informa: “Las líneas 2–15 se excluyen de la importación real”.

- [x] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`

Expected: FAIL porque la interfaz todavía analiza todas las filas en modo real y
mantiene un bloqueo constante.

- [x] **Step 3: Integrar el flujo aprobado**

Llamar `preview_csv` con:

```python
max_rows = 14 if test_mode else None
skip_rows = 0 if test_mode else 14
```

Eliminar `ADMINISTRATIVE_STORAGE_READY`, pasar `questionnaire` a
`import_preview` y conservar las condiciones existentes de autorización,
validación, mapeo y hash duplicado.

- [x] **Step 4: Actualizar documentación operativa**

Documentar que el catálogo está completo, las líneas 2–15 son pruebas excluidas,
la línea 16 inicia datos reales y los campos administrativos ya tienen
persistencia separada. No incluir ejemplos de respuestas.

- [x] **Step 5: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`

Expected: todas las pruebas de interfaz pasan.

### Task 6: Verificación integral sin importar datos reales

- [x] **Step 1: Validar el catálogo y sólo el encabezado real**

Ejecutar el chequeo existente de 105 encabezados y exigir: 105 aprobadas, 105
mapeadas, cero desconocidas, ambiguas u obligatorias faltantes. No abrir filas
de respuestas.

- [x] **Step 2: Ejecutar la suite completa**

Run: `.venv/bin/python -m pytest -v`

Expected: cero fallos y cero pruebas omitidas.

- [x] **Step 3: Ejecutar verificaciones estáticas**

Run: `.venv/bin/ruff check .`

Expected: `All checks passed!`

Run: `.venv/bin/python -m compileall -q app.py pages src tests`

Expected: código de salida 0 y sin salida.

- [x] **Step 4: Verificar arranque local**

Run: `timeout 12s .venv/bin/streamlit run app.py --server.headless true --server.port 8502`

Expected: el servidor inicia y se detiene por el límite, sin excepciones de la
aplicación.

- [x] **Step 5: Confirmar que no hubo escritura real**

Comprobar que `data/tamizaje.db` no fue creado durante las pruebas y reportar
explícitamente que la importación real requiere una acción posterior y
confirmación humana desde la interfaz.
