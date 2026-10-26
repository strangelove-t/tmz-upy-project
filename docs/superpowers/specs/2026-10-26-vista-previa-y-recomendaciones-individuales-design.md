# Vista previa fiel y recomendaciones editables por reporte

**Fecha:** 2026-10-26

**Estado:** diseño aprobado para planeación; implementación pendiente.

**Rama:** `feature/reportes-vista-previa-recomendaciones`

## Objetivo y alcance

La maestra debe poder revisar el contenido de los PDF antes de descargarlos y
ajustar las recomendaciones de un reporte individual concreto. La vista previa
será estructurada en Streamlit: reproducirá las secciones, textos y orden del
PDF, pero no su paginación ni su diseño milimétrico. No se incrustará un visor
PDF ni se añadirán dependencias para este fin.

La edición estará disponible para ambos tipos de la pestaña **Individual**:
reporte del alumno y expediente para tutor. La pestaña **Grupal** tendrá una
revisión de concordancia entre vista previa y PDF, sin edición. **Por lote** no
admitirá ediciones y seguirá utilizando las recomendaciones aprobadas del
catálogo. No habrá cambios en puntuación, semáforo, alertas ni casos.

## Comportamiento de la edición

- La maestra podrá modificar cada recomendación que efectivamente aparece en
  el PDF seleccionado. En el reporte del alumno son las áreas amarillas y
  rojas; en el del tutor se incluyen también las fortalezas verdes. No se
  inventarán recomendaciones para áreas sin resultado.
- Cada campo partirá del texto aprobado para ese destinatario. Al cambiarlo,
  la vista previa y el PDF descargable mostrarán inmediatamente el mismo texto.
  Un control **Restaurar recomendaciones originales** recuperará el catálogo
  para el contexto actual.
- Las modificaciones sólo vivirán en la sesión de Streamlit para la pareja
  `(submission_id, tipo_de_reporte)` activa. Al elegir otro alumno o tipo de
  reporte se descartarán; al cerrar la sesión tampoco quedarán guardadas.
  Cambiar la casilla de información sensible del tutor no descartará los textos.
- No se escribirá en `config/recommendations.csv`, SQLite, las plantillas ni el
  manifiesto. Las descargas por lote y otros reportes no heredarán cambios.
- Un texto vacío o sólo con espacios no será válido; la descarga se bloqueará
  hasta corregirlo o restaurarlo. El texto libre se tratará como texto, no
  como HTML ejecutable; la interfaz recordará no escribir diagnósticos en el
  reporte del alumno. No se prometerá detectar automáticamente información
  sensible introducida manualmente.

## Vista previa

La pestaña **Individual** construirá una sola versión de datos autorizados,
aplicará las ediciones temporales y utilizará ese mismo resultado tanto para
la vista previa como para renderizar el PDF. El nombre de archivo seguirá el
contrato actual. El registro de descarga conservará el tipo, versión y marca
de inclusión sensible actuales; no almacenará el texto editado.

Para el **alumno**, la vista previa reflejará el encabezado y la fecha, la
introducción, el resumen por colores, la explicación de la escala, las áreas
en el orden del PDF, las acciones sugeridas para amarillo/rojo, las fortalezas,
las áreas sin información, los recursos y el aviso final. No mostrará alertas,
casos, diagnósticos ni notas internas.

Para el **tutor**, mostrará encabezado y fecha, introducción, resumen, leyenda,
áreas con descripción e interpretación, acciones sugeridas agrupadas por
necesidades y fortalezas, aviso final y, sólo si la casilla está activada y
hay declaraciones pertinentes, la síntesis sensible que entrará en el PDF.
La casilla seguirá apagada por defecto y se reiniciará al cambiar alumno.

Para el **grupo**, se conservará el modelo `GroupReport` como fuente común.
La vista previa igualará las secciones y cifras del PDF: introducción,
alumnos evaluados, acompañamiento, solicitudes de contacto, semáforo, niveles,
áreas, focos de conversación, lista autorizada y aviso de confidencialidad.
Seguirá bloqueada para grupos por debajo de `minimum_group_size` y sin datos
sensibles individuales.

## Diseño técnico

`reports.py` seguirá siendo el límite de datos autorizados. Una función pura
aplicará sustituciones por `area_code` sobre una copia de `AreaLine` y
reconstruirá el campo `recommendations`; así no habrá dos versiones distintas
del texto dentro del mismo reporte. `pages/5_Reportes.py` conservará sólo el
estado temporal de los campos y presentará el contenido. Los renderizadores
PDF continuarán recibiendo los datos autorizados; no leerán el estado de la UI
ni el catálogo modificado. No se requiere migración de base de datos.

## Errores y verificación

- Si no hay recomendación aplicable, no se ofrecerá un editor vacío ni se
  añadirá una sección inexistente al PDF.
- Si un texto editado es inválido, la vista previa señalará el área y no
  ofrecerá un PDF desactualizado.
- Si falla la construcción o el renderizado, la página mostrará un error y no
  habilitará la descarga.
- Las pruebas usarán exclusivamente datos sintéticos y verificarán el mismo
  texto en vista previa y PDF, el aislamiento entre alumnos y destinatarios,
  la restauración, la descarga por lote sin cambios, el tratamiento seguro del
  texto y la ausencia de información sensible por defecto.
- La revisión final incluirá pruebas automatizadas, Ruff y una comparación
  manual de PDF sintéticos con las tres vistas previas.

## Fuera de alcance

No se edita el catálogo global, no se guardan borradores ni historial de
ediciones, no se envían reportes por correo y no se modifica la lógica de
prioridad o puntuación. La vista previa no será una réplica visual exacta de
la página impresa.
