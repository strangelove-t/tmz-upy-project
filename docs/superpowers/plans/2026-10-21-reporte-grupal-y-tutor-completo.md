# Reporte grupal y tutor completo — plan de implementación

**Diseño:** `docs/superpowers/specs/2026-10-21-reporte-grupal-y-tutor-completo-design.md`

## 1. Completar expediente para tutor

- Cambiar la prueba de `tests/test_reports.py` para exigir `A01`–`A09` en la
  lista blanca y ausencia de diagnósticos por defecto. Verificar el fallo.
- Ampliar `templates/tutor_report.json` a nueve áreas y subir la versión de
  plantilla. Verificar la prueba dirigida y la generación de PDF sintético.

## 2. Construir el resumen grupal

- Escribir pruebas sintéticas en `tests/test_group_report.py` para grupo de al
  menos cinco alumnos, grupo pequeño, alumnos con varias respuestas, promedios
  que excluyen resultados incompletos y ausencia de datos individuales.
- Implementar `src/tamizaje/group_report.py` con agregación desde envíos
  vigentes, modelo pequeño y PDF que incluya las mismas métricas.
- Ejecutar las pruebas dirigidas.

## 3. Añadirlo a Reportes

- Añadir pruebas en `tests/test_pages.py` para la pestaña **Grupal**, el bloqueo
  bajo `minimum_group_size` y la descarga del grupo permitido.
- Añadir selector, vista previa y botón PDF en `pages/5_Reportes.py`.
- Actualizar `README.md` y `docs/OPERACION_LOCAL.md` con el contenido y
  destinatario del reporte grupal y el alcance del expediente para tutor.

## 4. Cerrar

- Ejecutar la suite completa, Ruff, `compileall` y `git diff --check`.
- Renderizar un PDF grupal sintético y uno de tutor sintético; revisar su texto
  y distribución. Eliminar artefactos temporales.
- No utilizar la base real ni los CSV de `data/` durante pruebas o capturas.
