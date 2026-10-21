# Reportes legibles para tutoría — revisión aprobada

**Fecha:** 2026-10-21  
**Estado:** implementado; reemplaza el alcance de anonimato del
reporte grupal descrito en `2026-10-21-reporte-grupal-y-tutor-completo-design.md`.

## Alcance

El PDF grupal es un documento confidencial para el tutor del grupo. Conserva
agregados por área, pero ahora incluye exclusivamente a alumnos con caso abierto
para permitir acompañamiento concreto. No incluye correo, respuestas,
diagnósticos, categoría/motivo de alerta, notas ni estado del caso. Su lista
individual muestra nombre completo, nivel de atención, número de alertas y si
pidió contacto. Usa exactamente el orden de `Casos`, no una ordenación nueva
basada sólo en el número de alertas. La lista no se genera para grupos bajo
`minimum_group_size`.

## Lectura del reporte

Se elimina la cifra de «resultados completos» de pantalla y PDF. El reporte
abre con una explicación breve: qué se midió, cómo leer los semáforos y qué
significan los niveles de atención. Las nueve áreas llevan una descripción en
lenguaje común. Los promedios describen tendencias, no personas ni diagnósticos.
La sección de alumnos aparece como «Alumnos que requieren acompañamiento» y
explica que una alerta es una señal para conversar, no un diagnóstico. Se
mantienen los casos abiertos por nivel y las áreas con más amarillo/rojo.

Los textos de áreas y semáforos reutilizan `config/report_content.yaml`; allí
se configuran las explicaciones de niveles. La vista previa y el PDF parten
del mismo modelo para no divergir.

## Títulos, archivos y confidencialidad

El título del PDF grupal nombra el grupo y su archivo incluye el grupo y la
carrera. Los PDF individuales muestran nombre completo en el documento y
lo incluyen en el archivo, tanto para alumno como para tutor. Los nombres de
archivo se normalizan para Windows y reciben un sufijo corto para evitar
colisiones. El manifiesto de lote sigue apuntando a los nombres efectivamente
generados.

La interfaz advierte que el PDF grupal ahora contiene nombres. Su descarga
continúa en memoria, sin envío por correo. No se usa la base real en pruebas.

## Verificación

Pruebas sintéticas comprueban orden igual a `Casos`, sólo casos abiertos,
ausencia de datos prohibidos, textos explicativos, eliminación de cobertura,
nombres de archivo y el bloqueo de grupos pequeños. Se extrae texto y se
renderiza el PDF para revisar páginas y legibilidad.
