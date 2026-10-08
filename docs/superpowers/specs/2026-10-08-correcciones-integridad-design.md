# Correcciones de integridad posteriores a la integración

## Objetivo

Corregir cuatro hallazgos de la revisión del módulo de casos, reportes y grupos
sin alterar el modelo funcional del tamizaje ni perder seguimiento histórico.

## Diseño

### Casos recalculados sin alertas

La tabla `cases` incorporará `is_active`, con valor inicial `1`. El campo
representa si el caso sigue sustentado por las reglas activas, no el estado del seguimiento humano.

Cuando un recálculo produzca cero alertas, el caso existente se conservará con
sus notas y campos de seguimiento, pero pasará a `is_active = 0`. Las consultas
de priorización mostrarán únicamente casos activos. Si un recálculo posterior
vuelve a producir alertas, el mismo caso se actualizará y reactivará. Los casos
históricos seguirán accesibles desde el expediente individual.

`initialize_database` aplicará una migración aditiva e idempotente para bases
existentes que todavía no tengan la columna.

### Manifiesto CSV

Antes de escribir `correo` y `nombre`, se neutralizarán las celdas cuyo primer
carácter sea `=`, `+`, `-`, `@`, tabulador o retorno. Se antepondrá un apóstrofo,
el mecanismo compatible con hojas de cálculo que conserva el texto visible sin
ejecutarlo como fórmula. Los nombres de archivo, generados internamente, no
requieren esta transformación.

### Zona horaria de reportes

`parameters.yaml` declarará `report_timezone: America/Mexico_City`.
`EngineConfig` validará la zona mediante `zoneinfo.ZoneInfo`, de modo que pueda
cambiarse sin modificar código. La fecha impresa en los PDFs usará esa zona.

### Confidencialidad de grupos pequeños

Cuando el grupo seleccionado tenga menos de `minimum_group_size`, la página de
grupos ocultará tanto agregados como la tabla individual de estudiantes. El
expediente individual seguirá disponible en la página de estudiantes para el
personal autorizado.

## Compatibilidad y errores

- La migración no elimina ni reescribe casos existentes; se consideran activos.
- Una zona horaria inexistente impedirá cargar la configuración con un mensaje
  de contrato inválido.
- No se añaden dependencias: CSV y zona horaria usan la biblioteca estándar.
- No se modifica la separación de datos sensibles de los PDFs.

## Verificación

Se añadirán pruebas que demuestren:

1. desactivación y reactivación de un caso sin perder seguimiento ni notas;
2. exclusión de casos inactivos de la priorización;
3. neutralización de fórmulas en nombre y correo del manifiesto;
4. fecha generada en la zona configurada y rechazo de una zona inválida;
5. ausencia de la tabla individual en grupos menores al umbral.

Después se ejecutarán la suite completa, Ruff, compilación y una generación
visual sintética de ambos PDFs.
