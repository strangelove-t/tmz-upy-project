# Condiciones sensibles y reportes comprensibles

## Objetivo

Permitir que Orientación y Tutorías identifique condiciones declaradas de
neurodivergencia, salud emocional o mental, personalidad y salud física; que
pueda consultarlas de forma útil en Casos y Estudiantes; y que decida
explícitamente si las incluye en el expediente para tutor. Al mismo tiempo,
convertir los PDF actuales en documentos comprensibles que expliquen el
resultado, el semáforo y las acciones sugeridas.

## Decisiones aprobadas

- La información abarcará las secciones `ND`, `SE`, `AP` y `CF`.
- Se mostrará como una síntesis estructurada; las respuestas originales
  permanecerán disponibles únicamente en la vista protegida de Estudiantes.
- Existirá un solo aviso informativo consolidado por respuesta, con una etiqueta
  por cada categoría aplicable.
- El aviso no representa un puntaje bajo, no es una alerta de riesgo y no
  modifica scoring, semáforos, nivel, prioridad ni orden de los casos.
- El reporte destinado al alumno nunca incluirá diagnósticos ni condiciones de
  salud.
- **Expediente para asesor** se renombrará a **Expediente para tutor**.
- La sección sensible del expediente para tutor estará desactivada por defecto y
  sólo podrá incluirse mediante una decisión manual para cada generación.
- Preguntas, disparadores, etiquetas y contenido permitido serán configurables;
  no quedarán codificados directamente en las páginas o en el generador PDF.

## Principios de tratamiento

La aplicación presentará lo que el alumno declaró, sin confirmar ni inferir un
diagnóstico. Los textos usarán expresiones como **condición declarada**,
**diagnóstico declarado** y **confirmación profesional declarada**. La ausencia
de una respuesta afirmativa nunca se interpretará como ausencia clínica.

Se aplicará minimización de datos: las superficies de trabajo mostrarán primero
categoría, efecto actual y apoyo requerido. El diagnóstico específico sólo se
mostrará dentro del detalle individual autorizado y, en el PDF para tutor,
cuando la maestra active el control correspondiente.

No se utilizará contenido sensible para calcular riesgo ni para ordenar alumnos.
Los colores del semáforo conservarán exclusivamente su significado académico y
de permanencia. El aviso informativo utilizará un estilo neutral, distinto de
amarillo y rojo.

## Arquitectura

### Configuración declarativa

Se añadirá un archivo de configuración dedicado, por ejemplo
`config/sensitive_summary.yaml`, con versión propia. Para cada categoría
definirá:

- código estable: `neurodevelopment`, `mental_health`, `personality` o
  `physical_health`;
- etiqueta visible;
- pregunta que activa el aviso y respuestas consideradas afirmativas;
- preguntas que contienen diagnósticos o condiciones seleccionadas;
- campos de confirmación profesional, afectación actual, tratamiento,
  apoyos previos, apoyos solicitados y recomendaciones;
- etiqueta comprensible para cada campo;
- orden de presentación.

Los valores afirmativos se normalizarán con las utilidades existentes. La
configuración deberá poder admitir variantes del formulario sin cambiar las
páginas. Una respuesta diagnóstica presente podrá activar la categoría aunque
el indicador principal esté vacío o sea inconsistente; esa recuperación deberá
quedar marcada como dato que requiere revisión, no como confirmación clínica.

La carga será estricta: códigos inexistentes, categorías duplicadas, campos no
sensibles o predicados inválidos bloquearán la síntesis y mostrarán un error de
configuración sin exponer respuestas.

### Modelo de dominio

Un nuevo módulo enfocado, `src/tamizaje/sensitive_summary.py`, construirá un
objeto inmutable por `submission_id`. El contrato incluirá:

- `has_sensitive_declaration`;
- lista ordenada de categorías aplicables;
- resumen por categoría;
- indicador de apoyo o adecuación solicitada;
- indicador de afectación actual;
- advertencias de consistencia;
- versión de la configuración utilizada.

Cada categoría contendrá únicamente etiquetas y valores permitidos por la
configuración. Las páginas y reportes consumirán este objeto; no repetirán
consultas ni reglas de interpretación.

La primera versión calculará la síntesis desde `responses`, que ya conserva la
fuente canónica. No se duplicarán diagnósticos en `students`, `cases` ni una
tabla nueva. Esto evita divergencia y permite recalcular la presentación cuando
cambie la configuración.

## Aviso informativo

El aviso será una proyección independiente de las alertas y casos de riesgo. No
se insertará como regla en `alerts` y no creará por sí solo un registro en
`cases`, porque cualquiera de esas opciones contaminaría conteos y prioridades.

En Inicio se añadirá un indicador **Información declarada por revisar**, con el
número de respuestas vigentes que tengan al menos una categoría sensible. El
acceso llevará a Casos.

Casos incorporará una sección **Avisos informativos** antes o junto a la lista
operativa. Incluirá alumnos con declaración sensible aunque no tengan un caso de
riesgo. La lista mostrará únicamente nombre, grupo, categorías y si solicita
apoyo; no mostrará diagnósticos. Los alumnos que también tengan un caso
aparecerán una sola vez en la tabla operativa y mostrarán el indicador
**Información sensible: Sí**.

Al abrir un alumno con aviso se mostrará un bloque neutral:

> Información de salud o condición declarada por el alumno. No modifica la
> prioridad del caso ni constituye una valoración de la universidad.

El detalle se organizará en **Condiciones y apoyos**. El orden operativo de los
casos seguirá determinado únicamente por las reglas actuales.

## Estudiantes

La ficha individual tendrá cuatro pestañas: **Resultados**, **Seguimiento**,
**Condiciones y apoyos** y **Respuestas**.

La nueva pestaña mostrará una tarjeta por categoría aplicable con:

- condición o diagnóstico declarado;
- confirmación profesional, cuando el formulario la pregunte;
- afectación actual en estudios, asistencia o actividades;
- atención, tratamiento o seguimiento actual;
- apoyos o dispositivos utilizados;
- adecuaciones o apoyos solicitados;
- recomendaciones profesionales declaradas.

Si no existe una declaración aplicable, mostrará un estado vacío explícito. Si
hay respuestas contradictorias, mostrará **Requiere revisión de las respuestas**
sin intentar resolverlas automáticamente.

La pestaña **Respuestas** conservará su control cerrado por defecto para revelar
las respuestas sensibles originales. La síntesis no sustituye ni modifica la
fuente original.

## Reportes

### Destinatarios y nombres

Se conservarán dos productos:

1. **Reporte del alumno:** nunca contiene la síntesis sensible, incluso si un
   llamador intenta solicitarla.
2. **Expediente para tutor:** puede incluir la síntesis mediante autorización
   explícita.

El identificador interno nuevo será `tutor`, la plantilla será
`templates/tutor_report.json` y los archivos nuevos comenzarán con `tutor_`.
Los registros históricos cuyo `export_type` sea `advisor` no se reescribirán.
La documentación, interfaz y manifiesto usarán “tutor”.

### Control de inclusión

Al seleccionar el expediente para tutor aparecerá la casilla:

> Incluir condiciones de salud, neurodivergencias y diagnósticos declarados.

Estará desactivada por defecto. Activarla mostrará una advertencia de
confidencialidad y actualizará la vista previa antes de habilitar la descarga.
El valor volverá a `False` al cambiar de estudiante, tipo de reporte o sesión.

La generación por lote tendrá el mismo control, también desactivado, y una
confirmación adicional cuando se active. Todos los expedientes de un lote usarán
la misma elección y el resumen final indicará cuántos PDF sensibles se crearon,
sin enumerar condiciones.

La API de generación recibirá una opción explícita, por ejemplo
`include_sensitive=False`. El generador rechazará `include_sensitive=True` para
el reporte del alumno. La lista blanca de la plantilla seguirá siendo la última
barrera: una plantilla no autorizada no podrá extraer respuestas completas,
alertas, notas o correo.

### Auditoría

La tabla `exports` añadirá un campo booleano no nulo
`includes_sensitive_summary`, con valor predeterminado `0`. La inicialización
de la base aplicará una migración compatible a instalaciones existentes.

Cada descarga o generación por lote registrará tipo de reporte, versión de
plantilla y si incluyó la síntesis. La auditoría nunca guardará diagnósticos,
respuestas ni categorías concretas. Los PDF sensibles permanecerán en la misma
carpeta local ignorada por Git y no se ofrecerá descarga masiva desde la tabla.

## Contenido comprensible de los PDF

Ambos reportes tendrán una introducción breve que explique la finalidad del
tamizaje y que no constituye un diagnóstico. Incluirán una leyenda textual:

- **Verde — fortaleza:** recursos favorables que conviene mantener.
- **Amarillo — conviene dar seguimiento:** puede beneficiarse de orientación o
  apoyo preventivo.
- **Rojo — requiere atención:** conviene revisar el área y acordar acciones de
  apoyo.
- **Pendiente de revisión:** no hubo información suficiente para interpretar el
  área.

Cada resultado de área incluirá nombre, descripción breve configurable, puntaje
de 0 a 100, semáforo con texto, interpretación y acción sugerida. La
interpretación describirá el significado del rango sin afirmar causas ni
diagnósticos. La configuración de scoring o una configuración de presentación
asociada definirá las descripciones; el PDF no contendrá párrafos hardcodeados
por código de área.

Después se presentarán:

- fortalezas;
- aspectos que conviene atender;
- recomendaciones concretas adecuadas al destinatario;
- recursos institucionales autorizados;
- descargo de responsabilidad.

El expediente para tutor mantendrá sólo las áreas académicas autorizadas por su
plantilla. Cuando se active la opción sensible añadirá al final
**Condiciones y apoyos declarados**, con la síntesis estructurada y una marca
visible de **Confidencial — uso exclusivo de Orientación y Tutorías**.

## Vista previa

La vista previa de Reportes reflejará el contenido efectivo del PDF, incluyendo:

- explicación del semáforo;
- descripción e interpretación de cada área;
- fortalezas, necesidades y acciones sugeridas;
- presencia o ausencia de la sección sensible del tutor.

No bastará con mostrar la tabla actual. La maestra deberá poder comprobar antes
de descargar si el documento contiene datos sensibles.

## Errores y estados límite

- Sin respuestas sensibles aplicables: el aviso no aparece y el PDF no crea una
  sección vacía.
- Respuesta afirmativa sin condición especificada: mostrar **Condición declarada;
  detalle no especificado**.
- Selección diagnóstica sin respuesta afirmativa: activar el aviso con la marca
  **Requiere revisión de las respuestas**.
- Configuración inválida: bloquear únicamente las superficies y exportaciones
  que dependan de la síntesis; el reporte del alumno seguirá disponible.
- Área incompleta: explicar **Pendiente de revisión** y no convertir un valor
  faltante en cero.
- Fallo al generar un lote: conservar la política transaccional o de limpieza
  existente y no presentar el lote como completo.

Los mensajes de error no incluirán respuestas, diagnósticos, nombres ni correos.

## Pruebas y verificación

La implementación seguirá TDD y cubrirá al menos:

- carga y validación estricta de la configuración;
- activación individual y consolidada para `ND`, `SE`, `AP` y `CF`;
- ausencia de aviso con respuestas negativas;
- contradicciones y datos parciales;
- prueba de que la síntesis no modifica resultados, alertas, casos ni prioridad;
- alumnos con aviso informativo pero sin caso de riesgo;
- Casos con indicador discreto y detalle sólo al abrir al alumno;
- pestaña de Estudiantes y protección de respuestas originales;
- reporte del alumno incapaz de incluir información sensible;
- expediente para tutor sin sección sensible por defecto;
- inclusión manual reflejada en vista previa, PDF y auditoría;
- restablecimiento del control al cambiar alumno o destinatario;
- lote sensible con confirmación reforzada;
- migración de `exports` en una base existente;
- PDF con explicaciones, texto de semáforo y contenido que fluya entre páginas;
- extracción de texto del PDF para comprobar inclusiones y exclusiones;
- inspección visual de PDFs sintéticos con y sin sección sensible;
- suite completa, Ruff y `compileall`.

Las pruebas y capturas utilizarán datos sintéticos. No se copiarán diagnósticos
reales a fixtures, snapshots, logs ni documentación.

## Documentación y operación

Se actualizarán:

- guía de operación local;
- checklist de QA UX/UI;
- checklist de aceptación con la maestra;
- handoff del proyecto;
- explicación de privacidad y manejo de exportaciones;
- diccionario de la configuración sensible y de las descripciones de área.

La aceptación con la maestra incluirá localizar un aviso, abrir la síntesis en
Casos y Estudiantes, descargar un expediente sin datos sensibles, descargar otro
con inclusión explícita y distinguir ambos documentos sin abrir información de
otro alumno.

## Fuera de alcance

- Inferir diagnósticos a partir de puntajes o texto abierto.
- Validar clínicamente lo declarado.
- Cambiar scoring, umbrales, semáforos o prioridad por una condición de salud.
- Enviar reportes por correo o almacenarlos en servicios externos.
- Crear perfiles o permisos adicionales.
- Mostrar diagnósticos en tablas generales, Inicio, Grupos o el reporte del
  alumno.

## Criterios de aceptación

- Las cuatro categorías generan un único aviso consolidado y neutral.
- Un alumno puede producir un aviso aunque no tenga caso de riesgo, sin alterar
  métricas ni orden operativo.
- Casos y Estudiantes muestran una síntesis consistente desde una sola fuente.
- El reporte del alumno nunca contiene información sensible.
- El expediente para tutor la excluye por defecto y sólo la incluye después de
  una acción manual visible.
- Vista previa, PDF y auditoría coinciden respecto a la inclusión sensible.
- Los reportes explican semáforo, áreas, fortalezas, necesidades y acciones sin
  lenguaje diagnóstico.
- Los parámetros de activación y presentación pueden ajustarse mediante
  configuración validada.
- Las pruebas no usan ni revelan datos reales.
