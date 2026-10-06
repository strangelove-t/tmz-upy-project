# Motor de scoring configurable - diseño

## Objetivo

Calcular y persistir resultados de nueve áreas sin codificar en Python la
asignación de reactivos, respuestas, inversiones, exclusiones, pesos, umbrales
ni mínimos de completitud.

## Fuentes y alcance

El PDF canónico v1.2 define textos y opciones. El handoff define las nueve
áreas, 64 reactivos cuantitativos, fórmula, inversiones y codificaciones
especiales. Los catálogos versionados son la única entrada operativa del motor.

Esta fase calcula áreas y semáforos. No calcula puntaje global, alertas ni
recomendaciones textuales. `recommendation_code` queda preparado para una fase
posterior.

## Configuración

`parameters.yaml` contiene `active_scoring_version` y una sección por versión
con `scale_min`, `scale_max` y política de áreas incompletas.

`areas.csv` contiene `AreaCode`, nombre, conteo esperado, mínimo de reactivos
válidos, umbrales verde/amarillo y versión. Los umbrales pertenecen al área, no
se repiten globalmente.

`area_items.csv` relaciona área, `QuestionCode`, peso y versión. Es la única
fuente de pertenencia. En v0.2 los 64 pesos son `1`.

`scoring_options.csv` relaciona código, respuesta canónica, alias explícito,
valor corregido, inclusión en promedio y versión. La coincidencia es exacta
después de la normalización Unicode existente; no se permite similitud difusa.

Los CSV pueden conservar filas de varias versiones. El cargador selecciona la
versión activa y rechaza referencias inexistentes, duplicados normalizados,
pesos no positivos, valores fuera de escala, umbrales inválidos, conteos
inconsistentes y áreas sin cobertura.

## Cálculo

Por cada reactivo aplicable se obtiene un valor corregido y su peso. Las
respuestas con `IncludeInAverage=false` cuentan como exclusiones legítimas y no
entran al numerador ni al denominador.

```text
raw_average = sum(corrected_value * weight) / sum(weight)
normalized_score = ((raw_average - scale_min) / (scale_max - scale_min)) * 100
```

Se conserva precisión completa. El semáforo usa el resultado sin redondear:
verde desde `GreenMin`, amarillo desde `YellowMin`, rojo por debajo. Si
`ValidItemCount < MinimumValidItemCount`, el área queda incompleta y no recibe
puntaje ni semáforo.

Una respuesta faltante o no configurada nunca recibe un valor supuesto: deja el
área incompleta y genera una incidencia segura por código, sin incluir el valor.
No existe puntaje global.

## Persistencia y versionado

`area_results` usa la clave
`(submission_id, area_code, scoring_version)` y conserva promedio, puntaje,
semáforo, conteos, completitud y notas seguras. Una versión nueva crea resultados
nuevos; nunca sobrescribe otra versión. Recalcular la misma versión reemplaza de
forma transaccional únicamente esa versión.

Tras una importación correcta, la aplicación calculará las nueve áreas dentro
de la misma transacción. Un error de configuración o cálculo revierte también la
importación.

## Verificación

Las pruebas cubrirán catálogos inválidos, escala directa e invertida,
codificación especial, exclusión `No aplica`, ponderación, límites exactos,
área incompleta, respuesta desconocida, ausencia de puntaje global, persistencia
versionada y rollback. Sólo se usarán respuestas sintéticas.
