# UX/UI operativa para Tamizaje UPY

## Objetivo

Convertir la interfaz funcional existente en una herramienta clara para el
trabajo cotidiano de la maestra, manteniendo Streamlit, la operación local y
las garantías de confidencialidad. La interfaz debe responder primero qué
requiere atención, por qué y cuál es la siguiente acción.

## Alcance y principios

- Mantener Streamlit y la arquitectura actual.
- No modificar scoring, alertas, priorización ni contenido institucional como
  parte del rediseño.
- Usar componentes nativos y CSS compartido mínimo; no añadir frameworks de
  frontend, animaciones decorativas ni dependencias visuales.
- Reservar los colores de semáforo para estados y riesgo.
- Diseñar para una laptop institucional de 1366 × 768 y verificar también una
  pantalla amplia.
- No depender sólo del color para comunicar información.
- Mantener información sensible oculta de manera predeterminada.

## Arquitectura de navegación

Después de autenticarse, la aplicación abrirá en **Inicio**, no en la
importación. El menú quedará organizado según la frecuencia de uso:

1. Inicio
2. Casos
3. Estudiantes
4. Grupos
5. Reportes
6. Administración

La página principal actual se convertirá en Administración y conservará la
importación y el recálculo. El nuevo Inicio reutilizará las consultas existentes
para presentar pendientes y accesos directos, sin duplicar lógica de negocio.

## Sistema visual

`src/tamizaje/ui.py` concentrará estilos, etiquetas de estado y componentes
repetidos. La presentación usará:

- fondo claro y superficies discretamente delimitadas;
- jerarquía tipográfica consistente para título, sección, ayuda y dato;
- anchos y espaciados uniformes;
- botones primario, secundario y peligro con significado estable;
- etiquetas textuales junto con cualquier color de semáforo;
- iconografía profesional sólo cuando mejore el reconocimiento;
- textos breves, directos y sin terminología técnica innecesaria.

La identidad oficial de UPY se incorporará únicamente cuando existan colores,
logotipo y reglas de uso autorizados. Hasta entonces se utilizará una apariencia
institucional neutra.

## Inicio

La portada mostrará:

- fecha y contexto de operación;
- casos prioritarios abiertos;
- solicitudes expresas de contacto;
- seguimientos vencidos o próximos;
- alumnos procesados y fecha de última importación;
- lista breve de los siguientes casos por atender;
- distribución de casos por nivel;
- áreas con mayor necesidad de apoyo;
- acciones directas para revisar casos y buscar un estudiante.

Cada visualización debe apoyar una decisión. No se añadirán gráficas que sólo
repitan métricas o decoren la página.

## Casos

La vista de Casos será el centro de trabajo diario:

- filtros compactos y persistentes durante la sesión;
- prioridad, nivel, estado, solicitud de contacto y siguiente seguimiento
  visibles en la tabla;
- explicación de prioridad en lenguaje directo;
- panel de detalle dividido en motivo, contacto, seguimiento, notas y cierre;
- una acción primaria clara para guardar seguimiento;
- confirmación visible después de guardar;
- estados vacíos y errores con instrucciones concretas.

## Estudiantes

- Encabezado con nombre, carrera y grupo.
- Resumen compacto de las nueve áreas.
- Separación entre fortalezas y áreas de oportunidad.
- Historial de envíos legible y selección del vigente claramente indicada.
- Respuestas sensibles cerradas por defecto y advertencia antes de revelarlas.
- Acceso a los reportes desde el expediente.

## Grupos

- Selección clara de carrera y grupo.
- Tamaño y cobertura del grupo visibles.
- Promedios y distribución de semáforos con escalas consistentes.
- Lista priorizada sólo cuando se cumpla `minimum_group_size`.
- Mensaje explicativo, no técnico, cuando la confidencialidad impida mostrar
  resultados.

## Reportes

- Selección de estudiante y envío con contexto suficiente.
- Vista previa resumida antes de descargar.
- Acciones diferenciadas para reporte del alumno y expediente del asesor.
- Generación por lote acompañada de una advertencia de confidencialidad.
- Confirmación clara de los archivos generados y su ubicación local.

## Administración

- Última importación y versiones activas visibles al inicio.
- Carga de CSV presentada como un flujo guiado: archivo, validación, resumen y
  confirmación.
- Diferencia inequívoca entre modo de prueba y procesamiento real.
- Resumen de errores estructurales sin mostrar respuestas.
- Confirmación reforzada para importar datos reales.
- Recálculo separado visualmente como acción administrativa sensible.

## Estados de interacción

Todas las páginas cubrirán de forma explícita:

- cargando;
- sin datos;
- sin resultados para los filtros;
- validación incompleta;
- operación correcta;
- error recuperable;
- acción bloqueada por confidencialidad o autorización.

Los mensajes no incluirán nombres, correos, respuestas ni diagnósticos salvo en
las vistas individuales autorizadas.

## Accesibilidad

- Contraste suficiente para texto, controles y gráficas.
- Foco visible y orden de navegación por teclado.
- Etiquetas asociadas a todos los controles.
- Información de estado expresada mediante texto y color.
- Tablas utilizables sin desplazamiento horizontal evitable.
- Tamaños de interacción adecuados para uso cotidiano.
- Gráficas con títulos, ejes y leyendas comprensibles.

## Verificación UX/UI

El bloque se validará con datos sintéticos y con las líneas 2–15 permitidas:

1. pruebas de humo de las seis páginas;
2. recorrido acceso → Inicio → Casos → Estudiante → Reporte;
3. recorrido Administración → previsualización segura;
4. revisión visual a 1366 × 768 y pantalla amplia;
5. estados vacío, con datos, error y confidencialidad;
6. revisión de navegación por teclado y contraste;
7. capturas sólo con datos sintéticos;
8. inspección visual de PDFs;
9. sesión de aceptación con la maestra y registro de observaciones.

## Orden de ejecución

Este bloque se ejecutará después de implementar acceso local y el piloto
técnico, y antes de la instalación definitiva y la importación real. Se divide
en cinco entregas:

1. sistema visual y navegación;
2. Inicio y Casos;
3. Estudiantes, Grupos y Reportes;
4. Administración y estados de interacción;
5. QA visual, accesibilidad y aceptación con la maestra.

## Criterios de salida

- La maestra puede identificar la siguiente acción desde Inicio.
- Las tareas frecuentes requieren menos navegación que en la interfaz actual.
- Importación y recálculo quedan fuera del recorrido cotidiano.
- Las seis páginas comparten jerarquía, controles y mensajes consistentes.
- La interfaz funciona correctamente a 1366 × 768.
- Los controles sensibles conservan todas las restricciones existentes.
- No se introducen dependencias ni una segunda aplicación frontend.
- La maestra aprueba el recorrido antes de procesar datos reales.
