# Diseño de importación segura de CSV

## Objetivo

Implementar el primer flujo funcional del MVP: previsualizar, validar, confirmar
y persistir localmente una exportación CSV de Microsoft Forms, sin calcular
scoring, alertas, casos ni recomendaciones.

## Alcance

Este incremento soporta archivos CSV. El archivo disponible actualmente usa
codificación `cp1252`, separador `;`, 105 encabezados únicos y 65 líneas
físicas. La línea 1 contiene encabezados, las líneas 2 a 15 contienen 14
registros de prueba y desde la línea 16 existen datos reales confidenciales.

La división entre líneas de prueba y reales es una salvaguarda operativa del
archivo actual, no una regla general del importador. Las pruebas automatizadas
usarán fixtures sintéticos; no se copiarán filas del archivo real al repositorio.

Quedan fuera de este incremento:

- Importación XLSX.
- Mapeo de encabezados a `QuestionCode`.
- Validación de respuestas contra catálogos.
- Scoring, alertas, casos, recomendaciones y reportes.
- Visualización de respuestas individuales en la previsualización.

## Arquitectura

`normalization.py` contendrá funciones puras para Unicode NFC, espacios
exteriores y saltos de línea. `validation.py` definirá resultados estructurados
de validación sin incluir valores de respuestas. `importers.py` calculará el
SHA-256, detectará de forma cerrada `utf-8-sig`, `utf-8` o `cp1252`, detectará
el separador y producirá una previsualización en memoria.

`database.py` administrará la conexión, el esquema y una transacción única de
importación. `app.py` expondrá el flujo Streamlit de carga, previsualización y
confirmación. Ningún módulo registrará respuestas o encabezados completos en
logs.

## Flujo

1. La persona selecciona un CSV en Streamlit.
2. El sistema calcula SHA-256 sobre los bytes originales.
3. Se detectan codificación y separador usando una lista cerrada.
4. Se analizan encabezados y filas sin escribir en SQLite.
5. Se rechazan archivos vacíos, encabezados vacíos o duplicados y filas con una
   cantidad diferente de columnas.
6. Se consulta SQLite para advertir si el hash ya fue importado.
7. La interfaz muestra nombre, hash abreviado, codificación, separador, número
   de registros, número de columnas, errores y advertencias.
8. Sólo tras una confirmación explícita se inicia una transacción SQLite.
9. Se guarda una importación, un envío por fila y una respuesta por celda.
10. Un error revierte toda la transacción; el mismo hash no puede importarse dos
    veces.

## Persistencia

La base local será `data/tamizaje.db`, ignorada por Git. El esquema inicial
contendrá:

- `imports`: identificador, nombre de archivo, SHA-256 único, fecha, cantidad de
  filas, cantidad de columnas y estado.
- `submissions`: identificador, importación y número de fila de origen.
- `responses`: envío, encabezado original, encabezado normalizado, respuesta
  original y respuesta normalizada.

Este esquema conserva auditoría sin inventar todavía identificadores de alumno
o códigos de pregunta. Esos vínculos se añadirán cuando estén disponibles los
catálogos oficiales.

## Confidencialidad

- La previsualización nunca muestra valores de respuestas.
- Los mensajes de error identifican números de fila y conteos, no contenido.
- No se imprimen respuestas ni encabezados completos en consola o logs.
- La base y el CSV permanecen bajo `data/` y fuera de Git.
- La UI requiere confirmación explícita antes de procesar todas las filas.
- Para desarrollo con el archivo actual, un control permite limitar el análisis
  a las líneas 1–15; el modo completo debe advertir que incluye datos reales.
- Los fixtures versionados son enteramente sintéticos.

## Manejo de errores

Los errores bloqueantes impiden confirmar: archivo vacío, decodificación
fallida, separador no reconocido, encabezados vacíos o repetidos, y anchuras de
fila inconsistentes. Un hash ya importado también bloquea la escritura. Los
fallos de SQLite producen rollback y un mensaje genérico que no contiene datos.

## Pruebas

Las pruebas cubrirán:

- UTF-8, UTF-8 con BOM y `cp1252`.
- Normalización NFC, espacios y saltos de línea.
- SHA-256 determinista.
- CSV vacío, encabezados vacíos/duplicados y filas irregulares.
- Previsualización sin valores de respuestas.
- Creación del esquema, persistencia atómica y hash duplicado.
- Límite de líneas usado para desarrollo.

La aceptación requiere Pytest, Ruff y `compileall` sin errores, además de un
arranque headless de Streamlit.
