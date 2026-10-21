# Importación final desde la fila 2

**Fecha:** 2026-10-21  
**Estado:** aprobado

## Objetivo

Adecuar Administración al archivo de entrega: la línea 1 contiene encabezados
y todas las respuestas desde la línea 2 son datos reales. La interfaz final no
debe mostrar ni aplicar el antiguo modo para las 14 filas de prueba.

## Decisiones

- Eliminar el interruptor **Modo de prueba** de Administración.
- Previsualizar siempre el CSV completo desde la primera respuesta, sin omitir
  filas y sin guardar durante la validación.
- Mantener la autorización escrita, la casilla de confirmación y la frase
  `IMPORTAR` antes de persistir datos reales.
- Mantener intactas la transacción, la validación de estructura y la protección
  contra identificadores duplicados.
- Mostrar en el resumen el total real de registros que se intentará importar y
  el rango correcto de líneas de origen.
- Actualizar únicamente la documentación operativa vigente. Los planes,
  especificaciones y handoffs antiguos conservarán la regla de líneas 2–15 como
  evidencia histórica, no como instrucción actual.
- Conservar el piloto técnico y sus scripts para soporte; deja de formar parte
  del recorrido normal de la maestra.

## Flujo final

1. La maestra abre **Administración** y selecciona el CSV original de Forms.
2. La aplicación analiza encabezados y todas las respuestas desde la línea 2.
3. Si la estructura o el mapeo fallan, la importación permanece bloqueada.
4. Si la validación pasa, se muestra el número total de registros y su rango de
   líneas, sin exponer respuestas en mensajes o consola.
5. La maestra confirma que existe autorización escrita y escribe `IMPORTAR`.
6. La aplicación guarda el lote completo dentro de una sola transacción. Ante
   cualquier duplicado o error, no persiste cambios parciales.

## Archivos en alcance

- `pages/6_Administracion.py`: retirar el modo de prueba y usar `skip_rows=0`.
- `tests/test_pages.py`: verificar ausencia del control y procesamiento desde
  la primera respuesta.
- `README.md`, `docs/OPERACION_LOCAL.md`,
  `docs/checklists/ACEPTACION_PILOTO.md` y `docs/HANDOFF_2026-10-08.md`:
  conciliar las instrucciones vigentes con el formato final.

No se cambiarán `src/tamizaje/importers.py`, el esquema de base, el scoring, las
alertas, los reportes ni la lógica de duplicados.

## Manejo de errores y confidencialidad

- La validación previa no escribe en SQLite.
- Los mensajes sólo muestran conteos, líneas y errores estructurales seguros.
- Nombres, correos, respuestas e identificadores no se imprimen ni se copian a
  pruebas o documentación.
- La importación real continúa bloqueada hasta completar ambas confirmaciones.

## Verificación

- Prueba roja que demuestre que la interfaz todavía muestra el modo de prueba o
  excluye las primeras 14 respuestas.
- Prueba verde que confirme que la carga parte de la línea 2 y que no existe el
  interruptor.
- Suite completa, Ruff, `compileall` y `git diff --check`.
- Revisión manual con un CSV sintético; no usar datos reales en fixtures,
  capturas ni salidas de prueba.

## Fuera de alcance

- Importación incremental de exportaciones acumulativas.
- Cambios al tratamiento de duplicados.
- Eliminación de scripts históricos de aceptación.
- Importación automática sin autorización explícita.
