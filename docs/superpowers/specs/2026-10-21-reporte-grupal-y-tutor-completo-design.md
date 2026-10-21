# Reporte grupal y expediente completo para tutor

**Fecha:** 2026-10-21  
**Estado:** aprobado en conversación

## Destinatario y alcance

El reporte grupal se descarga como PDF desde **Reportes** y se entrega al tutor
del grupo mediante los canales institucionales. Resume el grupo elegido por
carrera y grupo. La aplicación no envía correo.

El expediente individual para tutor pasa de cuatro a las nueve áreas del
instrumento. Cada área conserva puntaje, semáforo, interpretación y acción
sugerida. No se añaden respuestas por pregunta, alertas, notas ni seguimiento
en esta fase. La síntesis de condiciones y diagnósticos sigue excluida por
defecto y sólo aparece al activar la casilla existente.

## Reporte grupal

- Usa exclusivamente la respuesta vigente de cada alumno.
- Muestra fecha, carrera, grupo, número de alumnos evaluados y cobertura de
  resultados completos.
- Para las nueve áreas muestra promedio de resultados completos (0–100) y
  distribución de alumnos en verde, amarillo, rojo y sin resultado completo.
- Muestra el total de casos abiertos por nivel de atención y las áreas con más
  alumnos en amarillo o rojo como punto de partida para la tutoría.
- Explica que un promedio no es diagnóstico ni describe a cada estudiante.
- No contiene nombres, correos, respuestas, diagnósticos ni filas individuales.
- Si el grupo tiene menos de `minimum_group_size`, bloquea vista previa y PDF,
  igual que la página **Grupos**.
- El botón descarga el PDF en memoria. No modifica expedientes ni crea archivos
  automáticamente en `exports/`.

## Arquitectura

`src/tamizaje/group_report.py` construye un modelo agregado a partir de SQLite
y lo renderiza a PDF. Usa las áreas y niveles de la configuración activa.
`pages/5_Reportes.py` añade la pestaña **Grupal** con selector de carrera y
grupo, vista previa resumida y descarga.

`templates/tutor_report.json` enumera las nueve áreas y aumenta su versión.
El código actual de `reports.py` ya aplica la lista de áreas de la plantilla y
genera tanto la vista previa como el PDF y los lotes; no se amplía su lista
blanca de campos sensibles.

## Errores y verificación

Grupo inexistente o menor al umbral: no se genera PDF. Resultados incompletos:
se cuentan como pendientes y no se promedian como cero. Las pruebas usan sólo
CSV sintéticos para verificar tamaño mínimo, respuesta vigente, nueve áreas,
concordancia de la vista previa y contenido PDF, además de la protección
individual ya existente.
