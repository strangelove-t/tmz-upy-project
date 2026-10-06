# Persistencia normalizada de importaciones

## Objetivo

Importar respuestas reales desde la línea 16 del CSV y persistir por separado
identidad del alumnado, metadatos de envío y respuestas del cuestionario, sin
exponer datos sensibles en interfaz, pruebas o logs.

## Alcance

- Omitir siempre las 14 filas de prueba durante una importación real.
- Conservar sus números de línea originales para auditoría.
- Identificar a cada estudiante por correo institucional normalizado.
- Conservar cada envío; nunca sobrescribir un envío anterior.
- Marcar un segundo envío del mismo correo para revisión.
- Impedir envíos duplicados por identificador externo de Microsoft Forms.
- Ejecutar toda la escritura en una sola transacción SQLite.
- Mantener el modo seguro actual, que analiza únicamente las filas 2–15 y nunca
  permite persistirlas.

No se incluye todavía scoring, resolución manual de duplicados, cifrado a nivel
de campo ni importación XLSX.

## Modelo de datos

`imports` conserva nombre, hash SHA-256, fecha, versiones, número de registros y
estado. El hash sigue evitando procesar dos veces el mismo archivo completo.

`students` conserva correo normalizado único, correo original, nombre, carrera y
grupo. Un nuevo envío del mismo correo reutiliza al estudiante. El nombre,
carrera y grupo existentes no se sobrescriben automáticamente.

`submissions` conserva identificador externo único, estudiante, importación,
línea de origen, fechas de inicio y finalización, vigencia y marca de duplicado.
El primer envío de un estudiante queda vigente; los posteriores quedan no
vigentes y marcados para revisión.

`responses` conserva envío, `QuestionCode`, valor original, valor normalizado y
marca de sensibilidad. Los códigos `ADM_*`, `DG02` y `DG03` no se duplican en
esta tabla porque se almacenan en sus entidades especializadas.

## Mapeo de columnas

- `ADM_EMAIL` → identidad y clave natural de `students`.
- `ADM_NAME` → nombre de `students`.
- `DG02` → carrera de `students`.
- `DG03` → grupo de `students`.
- `ADM_RESPONSE_ID` → clave externa de `submissions`.
- `ADM_STARTED_AT` → fecha de inicio de `submissions`.
- `ADM_COMPLETED_AT` → fecha de finalización de `submissions`.
- Los otros códigos aprobados → `responses`.

La importación exige el catálogo aprobado y un mapeo válido. Los valores
administrativos requeridos deben estar presentes y no vacíos. Las fechas se
conservan como texto de origen en esta fase para evitar interpretar con una zona
horaria incorrecta.

## Selección y numeración de filas

`preview_csv` recibirá `skip_rows`. En modo real usará `skip_rows=14`; en modo
seguro usará `max_rows=14` y `skip_rows=0`. `CsvPreview` incluirá los números de
línea de origen de cada fila, de modo que la primera fila real conserve el número
16. Una previsualización limitada seguirá sin ser persistible; omitir las filas
de prueba no convertirá la previsualización real en limitada.

## Duplicados y transacciones

El correo se normaliza con la función Unicode existente y `casefold()`. Si ya
existe, se reutiliza el estudiante. Si ya existe el identificador externo del
envío, se aborta la importación completa. Si el correo tiene un envío anterior,
el nuevo se guarda con `duplicate_student_submission = 1` e `is_current = 0`.

Cualquier validación o error SQLite revierte `imports`, `students`,
`submissions` y `responses`. Los mensajes públicos indican únicamente el tipo de
problema y, cuando sea útil, el número de línea; nunca muestran valores.

## Interfaz y seguridad

La interfaz explicará que las líneas 2–15 se excluyen de la importación real y
mostrará el número de registros reales analizados. La confirmación seguirá
requiriendo autorización explícita. El botón se habilitará únicamente cuando la
validación y el mapeo sean válidos y el hash no exista.

## Verificación

Las pruebas usarán datos enteramente sintéticos y cubrirán: exclusión de 14
filas, conservación de la línea 16, separación de campos, reutilización de un
estudiante, segundo envío marcado, identificador externo duplicado, rollback y
ausencia de valores sensibles en representaciones públicas. La entrega exige
Pytest, Ruff, `compileall` y arranque headless de Streamlit.
