# Acceso local y piloto operativo controlado

## Objetivo

Restringir la aplicación instalada en la computadora de la maestra a una sola
contraseña local y ejecutar la aceptación funcional con los registros de prueba
de las líneas 2–15, sin exponer ni importar los datos reales de la línea 16 en
adelante antes de la aprobación institucional.

## Alcance de acceso

La aplicación no tendrá perfiles ni roles. Streamlit escuchará exclusivamente
en `127.0.0.1`, por lo que no aceptará conexiones desde otras computadoras. Una
pantalla de acceso bloqueará la aplicación completa hasta validar una contraseña
compartida para la instalación local. El equipo de desarrollo conserva acceso al
código y brinda soporte, pero no requiere otra identidad dentro de la aplicación.

La contraseña nunca estará en Git. El archivo local
`.streamlit/secrets.toml` guardará únicamente sal, parámetros y hash derivado
con `hashlib.scrypt`. La comparación usará `hmac.compare_digest`. Se incluirá
un comando local para generar o reemplazar el secreto y un ejemplo sin valores
reales. La sesión autenticada vivirá sólo en `st.session_state` y tendrá un botón
de cierre.

## Límites de datos

- `data/`, `exports/` y `.streamlit/secrets.toml` permanecerán ignorados.
- Las pruebas automatizadas y evidencias usarán exclusivamente datos sintéticos.
- La aceptación operativa procesará sólo las líneas 2–15 del CSV local mediante
  el modo seguro existente.
- Ningún valor de respuesta, nombre, correo o diagnóstico se copiará a logs,
  documentación, commits o mensajes.
- La importación desde la línea 16 seguirá bloqueada hasta que la maestra valide
  los contenidos institucionales y firme el checklist de autorización.

## Flujo de aceptación

1. Confirmar que el servidor sólo responde en `127.0.0.1`.
2. Verificar rechazo de contraseña incorrecta, acceso correcto y cierre de
   sesión.
3. Ejecutar la suite automatizada completa.
4. Previsualizar el CSV local en modo seguro y confirmar que sólo se consideran
   las líneas 2–15, usando exclusivamente conteos y números de línea.
5. Importar esos registros de prueba en una base de aceptación separada.
6. Validar scoring, alertas, casos, recálculo, umbral de grupos y reportes sin
   imprimir valores sensibles.
7. Generar PDFs de control para inspección visual y eliminar las evidencias
   temporales al terminar.
8. Registrar el resultado en un checklist operativo sin datos personales.

## Operación y recuperación

Se documentará una guía para iniciar y detener la aplicación, cambiar la
contraseña, respaldar `data/tamizaje.db`, restaurar una copia y manejar
`exports/`. La guía indicará bloquear la sesión de Windows, restringir el acceso
físico, conservar el CSV original fuera del repositorio y no sincronizar datos
sensibles en servicios no autorizados.

## Criterios de salida

- Acceso local y contraseña verificados por pruebas.
- Cero datos sensibles rastreados por Git o emitidos durante la aceptación.
- Suite, Ruff y compilación aprobados.
- Piloto de líneas 2–15 completado o incidencia documentada.
- Checklist institucional listo, con la importación real explícitamente marcada
  como no autorizada hasta obtener la aprobación de la maestra.
