# Importación segura de CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Previsualizar, validar y persistir transaccionalmente exportaciones CSV locales sin exponer respuestas sensibles.

**Architecture:** Funciones puras normalizan y validan; el importador crea una previsualización inmutable en memoria; SQLite persiste la previsualización sólo tras confirmación. Streamlit muestra metadatos y conteos, nunca respuestas.

**Tech Stack:** Python 3.12, biblioteca estándar (`csv`, `hashlib`, `sqlite3`, `unicodedata`), Streamlit, Pytest y Ruff.

---

### Task 1: Normalización y validación estructural

**Files:**
- Modify: `src/tamizaje/normalization.py`
- Modify: `src/tamizaje/validation.py`
- Modify: `tests/test_import.py`

- [ ] **Step 1: Escribir pruebas fallidas**

Probar NFC, conversión CRLF/CR a LF, espacios exteriores, archivo vacío,
encabezados vacíos/duplicados normalizados y filas de anchura irregular. Los
errores sólo contienen código, mensaje seguro y número de fila.

- [ ] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: FAIL por funciones inexistentes.

- [ ] **Step 3: Implementar lo mínimo**

Crear `normalize_text`, `ValidationIssue`, `ValidationResult` y
`validate_table`. No incluir valores de celdas en mensajes o representaciones.

- [ ] **Step 4: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: todas las pruebas del bloque pasan.

### Task 2: Previsualización CSV segura

**Files:**
- Modify: `src/tamizaje/importers.py`
- Modify: `tests/test_import.py`
- Modify: `tests/fixtures/synthetic_responses.csv`

- [ ] **Step 1: Añadir pruebas fallidas**

Cubrir SHA-256, UTF-8, BOM, `cp1252`, separador, límite de filas y ausencia de
respuestas en `repr(preview)` y `preview.summary()`.

- [ ] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: FAIL por API del importador inexistente.

- [ ] **Step 3: Implementar previsualización**

Crear `CsvPreview`, `ImportErrorSafe`, `sha256_bytes`, `detect_encoding`,
`detect_delimiter` y `preview_csv`. Conservar filas sólo en un atributo oculto
del resumen y de `repr` para su posterior persistencia.

- [ ] **Step 4: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: todas las pruebas pasan.

### Task 3: Persistencia transaccional e idempotente

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `tests/test_import.py`

- [ ] **Step 1: Añadir pruebas fallidas**

Probar creación del esquema, persistencia de conteos y respuestas, detección de
hash duplicado y rollback completo ante un error inducido.

- [ ] **Step 2: Verificar RED**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: FAIL por API de base inexistente.

- [ ] **Step 3: Implementar SQLite**

Crear `connect_database`, `initialize_database`, `is_imported` e
`import_preview`, con claves foráneas, SHA-256 único y una sola transacción.

- [ ] **Step 4: Verificar GREEN**

Run: `.venv/bin/python -m pytest tests/test_import.py -v`
Expected: todas las pruebas pasan.

### Task 4: Flujo Streamlit

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Implementar carga y previsualización**

Agregar `file_uploader`, modo seguro predeterminado limitado a 14 registros,
resumen de metadatos y errores/advertencias sin respuestas.

- [ ] **Step 2: Implementar confirmación**

En modo de prueba permitir sólo previsualización. Para importar todo el archivo,
exigir una casilla explícita de autorización, bloquear errores/hash duplicado y
crear `data/tamizaje.db` al pulsar el botón.

- [ ] **Step 3: Verificar arranque**

Run: `.venv/bin/python -m streamlit run app.py --server.headless true --server.port 8502`
Expected: URL local sin traceback.

### Task 5: Verificación final

**Files:**
- Modify only if verification exposes a defect.

- [ ] **Step 1: Validar con el segmento de prueba del archivo disponible**

Ejecutar `preview_csv` con límite 14 y mostrar sólo resumen de metadatos. Esperar
105 columnas, 14 registros y cero errores estructurales.

- [ ] **Step 2: Ejecutar suite y análisis estático**

Run: `.venv/bin/python -m pytest -v`
Expected: todas las pruebas pasan.

Run: `.venv/bin/python -m ruff check .`
Expected: `All checks passed!`.

Run: `.venv/bin/python -m compileall -q app.py pages src tests`
Expected: exit code 0.

- [ ] **Step 3: Revisar seguridad Git**

Run: `git check-ignore data/tamizaje.db data/*.csv data/*.xlsx`
Expected: las rutas de datos están ignoradas.

- [ ] **Step 4: Entregar sin commit**

No crear commit ni publicar al remoto.
