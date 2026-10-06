# Incidente PE02: semestre vs. cuatrimestre

## Resumen

El 6 de octubre de 2026, durante la conciliación del formulario con el CSV de
respuestas, se detectó una diferencia en la pregunta 92 (`PE02`). La versión
anterior preguntaba por la continuidad durante el “próximo semestre”. Esa
redacción era incorrecta porque la Universidad Politécnica de Yucatán opera por
cuatrimestres.

La versión 1.2 del formulario corrige la redacción a “próximo cuatrimestre” y se
establece como fuente canónica.

## Alcance

- Código afectado: `PE02`.
- Versión histórica: anterior a 1.2.
- Versión corregida: 1.2.
- Scoring: permanece en versión 0.2.
- Opciones de respuesta: no cambian.
- Respuestas históricas: no se modifican ni se reinterpretan silenciosamente.

Aunque las opciones y su valor corregido no cambian, el periodo de referencia
sí cambia. Por ello, los resultados de versiones anteriores deben conservar su
versión de cuestionario para que cualquier comparación longitudinal considere
esta diferencia semántica.

## Corrección aplicada

1. `questionnaire.csv` define como texto canónico “próximo cuatrimestre” para
   `PE02` y `QuestionnaireVersion = 1.2`.
2. `questionnaire_aliases.csv` registra “próximo semestre” como alias histórico
   exacto de `PE02`, con versión de origen `pre-1.2`.
3. El importador acepta el alias sólo por coincidencia exacta; no utiliza
   coincidencia difusa.
4. Se conserva el encabezado original del CSV en auditoría.
5. El borrador marca la columna histórica como alias aprobado, sin reemplazar su
   texto original.

## Prevención

- Toda modificación de redacción debe incrementar la versión del cuestionario.
- Las variantes históricas deben registrarse explícitamente como alias.
- Las importaciones deben conservar versión, encabezado original y código
  canónico por separado.
- No se deben mezclar agregados entre versiones sin indicar el cambio de periodo
  de referencia.
