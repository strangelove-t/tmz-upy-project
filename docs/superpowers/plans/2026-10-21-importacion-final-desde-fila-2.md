# Importación final desde la fila 2 — plan de implementación

**Diseño aprobado:** `docs/superpowers/specs/2026-10-21-importacion-final-desde-fila-2-design.md`

## 1. Probar el flujo final

- En `tests/test_pages.py`, cambiar la prueba de Administración para exigir que
  no aparezca el control de prueba.
- Con un CSV sintético de 16 respuestas, exigir que el resumen indique 16 y que
  el botón de importación esté deshabilitado antes de confirmar.
- Tras la casilla y `IMPORTAR`, exigir que SQLite tenga las líneas fuente 2–17.
- Ejecutar esas pruebas y comprobar que fallen por el comportamiento anterior.

## 2. Cambiar Administración

- En `pages/6_Administracion.py`, retirar `TEST_DATA_ROWS`, el interruptor y
  sus mensajes.
- Llamar a `preview_csv` sin límite ni filas omitidas. La validación no escribe
  en la base hasta la confirmación existente.
- Mantener intacto `import_preview`, la autorización y el rechazo de duplicados.
- Ejecutar las pruebas modificadas y comprobar que pasen.

## 3. Conciliar documentación vigente

- Actualizar `README.md`, `docs/OPERACION_LOCAL.md`,
  `docs/checklists/ACEPTACION_PILOTO.md` y `docs/HANDOFF_2026-10-08.md` para
  indicar encabezado en línea 1 y datos desde línea 2. Evitar cifras de la
  base que puedan quedar obsoletas tras una importación.
- Etiquetar el piloto de 14 filas como histórico y no aplicable al archivo
  final. Conservar scripts y diseños anteriores para consulta.
- Mantener sin cambios la edición previa del usuario en la especificación de
  2026-10-08.

## 4. Verificar

- Ejecutar `.venv/bin/pytest -q`, `.venv/bin/ruff check .`,
  `.venv/bin/python -m compileall -q app.py pages src scripts tests` y
  `git diff --check`.
- Confirmar que Git sólo rastrea los `.gitkeep` de `data/` y `exports/`.
- No importar archivos reales durante la verificación.
