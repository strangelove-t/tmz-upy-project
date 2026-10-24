# Tamizaje y Orientación UPY

Aplicación local para procesar por lote respuestas exportadas de Microsoft
Forms. El instrumento orienta el seguimiento institucional; no produce
diagnósticos psicológicos ni clínicos.

## Requisitos

- Python 3.12 o 3.13
- Una computadora institucional con cifrado de disco
- El repositorio configurado como privado

## Preparación

En PowerShell o una terminal ubicada en el repositorio:

```bash
python -m venv .venv
```

Activa el entorno en Windows:

```powershell
.venv\Scripts\Activate.ps1
```

O en Linux y macOS:

```bash
source .venv/bin/activate
```

Instala el proyecto y sus herramientas de desarrollo:

```bash
python -m pip install -e ".[dev]"
```

## Contraseña local

La aplicación completa está protegida por una sola contraseña, sin usuarios,
perfiles ni roles. Antes del primer inicio:

```bash
python scripts/set_local_password.py
```

Sólo se guarda sal + hash `scrypt` en `.streamlit/secrets.toml` (ignorado por
Git). El equipo de desarrollo no necesita una identidad dentro de la
aplicación instalada.

## Ejecución

```bash
python -m streamlit run app.py
```

En Windows también se puede usar `run_windows.bat` después de preparar `.venv`.
Streamlit escucha sólo en `http://127.0.0.1:8501`; ninguna otra computadora
puede conectarse. Inicio, cierre, cambio de contraseña, respaldo, restauración
y manejo de exportaciones están en `docs/OPERACION_LOCAL.md`.

## Piloto histórico

`scripts/run_acceptance.py` se conserva para reproducir el piloto histórico de
14 filas con un archivo de prueba aislado. No debe ejecutarse con la exportación
operativa actual: sus filas desde la línea 2 son datos reales. Para validar un
archivo actual, cárgalo en **Administración**; la previsualización no lo guarda.

Con un archivo de prueba preparado específicamente para ese piloto:

```bash
python scripts/run_acceptance.py
```

El script procesa sólo las líneas 2–15 en una base temporal y muestra
únicamente conteos. No interviene en la importación normal.

## Verificación

```bash
python -m pytest
python -m ruff check .
```

## Fuentes de verdad

El diccionario v1.2, el scoring v0.2, las 44 reglas de alerta v0.1, las
recomendaciones, la síntesis sensible y el contenido explicativo de reportes
están disponibles en `config/`. Las
plantillas de reportes (lista blanca de campos) están en `templates/`. Consulta
`config/README.md` antes de cambiar una regla.

## Guía breve de uso

`run_windows.bat` abre el navegador automáticamente. Para terminar se usa el
botón **Salir de la aplicación**, que cierra la sesión y apaga el servidor.
Después de escribir la contraseña, el menú lateral muestra siete páginas,
ordenadas por frecuencia de uso:

1. **Inicio**: casos prioritarios, solicitudes de contacto, seguimientos
   vencidos, los siguientes cinco casos por atender y las áreas con más
   necesidad. Es el punto de partida diario.
2. **Casos**: lista priorizada con búsqueda y filtros (se conservan durante la
   sesión). Un clic en cualquier celda de una fila abre el caso, con pestañas
   *Motivo y alertas*, *Seguimiento* (contacto, estado, canalización y cierre)
   y *Notas*. El motivo de la prioridad se explica en lenguaje cotidiano. La
   columna *Condición declarada* indica qué categorías declaró el alumno.
3. **Condiciones declaradas**: alumnos que declararon neurodivergencia, salud
   emocional o mental, personalidad o condición física, sensorial o de salud,
   tengan o no un caso abierto. Muestra un conteo por condición y filtros
   visibles por condición, solicitud de apoyo, nombre, carrera y grupo (se
   conservan durante la sesión). El diagnóstico declarado sólo aparece al hacer
   clic en un alumno; la tabla nunca lo muestra. No modifica la prioridad.
4. **Estudiantes**: expediente con pestañas *Resultados* (nueve áreas,
   fortalezas, oportunidades y recomendaciones), *Seguimiento* y *Respuestas*
   (las sensibles quedan ocultas hasta activarlas). Si hay varios envíos, aquí
   se elige el vigente. La pestaña *Condiciones y apoyos* resume declaraciones
   de salud sin modificar la prioridad. **Ver reportes del alumno** abre
   Reportes con el mismo alumno.
5. **Grupos**: promedios y semáforos por carrera y grupo. Los grupos con menos
   alumnos que `minimum_group_size` no muestran agregados ni la lista.
6. **Reportes**: en cada pestaña el botón de descarga o generación va arriba
   y debajo la vista previa, donde se editan los textos (no cifras, semáforos
   ni nombres) y se agregan notas al PDF. Las ediciones se guardan en la tabla
   `report_edits` por alumno o grupo —sólo lo que difiere del original— y las
   usan la descarga individual y el lote (`tamizaje.report_edits`). Pestaña
   *Individual* con vista previa y descarga; pestaña
   *Grupal* con informe PDF para el tutor del grupo: explica las nueve áreas,
   semáforos y niveles, y lista sólo a alumnos con atención abierta en el orden
   de **Casos** (nombre, nivel, alertas y solicitud de contacto), sin respuestas,
   motivos ni diagnósticos. Se bloquea bajo
   `minimum_group_size`; pestaña *Por lote* con advertencia de
   confidencialidad, generación en `exports/` y manifiesto `correo → archivo`.
   Los tres PDF (**Reporte de orientación** del alumno, **Expediente para
   tutor** y **reporte grupal**) comparten la identidad de la UPY definida en
   `src/tamizaje/pdf_brand.py`: logo, morado `#5B0A8A`, acento naranja
   `#FDA20C`, tipografía Lato de `assets/`, tarjetas de resumen y cifras enteras
   de 0 a 100 con barra (se trunca: 69.6 se muestra 69 y nunca cruza un
   umbral). El reporte del alumno da recomendaciones sólo para áreas en
   amarillo o rojo y nunca incluye diagnósticos. El expediente para tutor —el
   mismo en descarga individual y por lote— ordena las nueve áreas de lo más
   urgente a lo menos, muestra acciones sugeridas y permite incluir una síntesis
   sensible mediante una casilla apagada por defecto. El reporte grupal colorea
   cada promedio con los umbrales del área. El
   PDF grupal contiene nombres, se descarga en memoria para compartirlo sólo
   con el tutor por un canal institucional autorizado y no se envía por correo.
   Los archivos individuales incluyen el nombre completo y los grupales el
   grupo en el nombre del archivo. La fecha usa
   `report_timezone` y
   las celdas del manifiesto se protegen contra fórmulas de hojas de cálculo.
7. **Administración**: importación en cuatro pasos (Archivo, Validación,
   Resumen, Confirmación). La validación analiza todas las respuestas desde la
   línea 2 sin guardarlas; importar exige autorización escrita, una casilla y
   escribir `IMPORTAR`. Aquí también está **Recalcular resultados**, que
   aplica una versión nueva de scoring o de reglas a los envíos guardados sin
   reimportar. Un caso sin alertas vigentes conserva su historial, pero sale de
   la priorización.

## Confidencialidad

- No uses datos reales en commits, issues, pruebas, capturas o pull requests.
- Conserva las exportaciones originales fuera del repositorio, en almacenamiento
  institucional autorizado y restringido.
- No sincronices bases o reportes con cuentas personales.
- Cierra la aplicación antes de copiar o respaldar SQLite.
- No publiques este repositorio.

### Archivo de respuestas disponible

En la exportación operativa actual:

- La línea 1 contiene los encabezados.
- Todas las respuestas desde la línea 2 son datos reales, sensibles y
  confidenciales; Administración las incluye desde esa primera línea.
- La base local puede contener importaciones operativas. No debe utilizarse
  para desarrollo, pruebas o capturas.
- Las pruebas y demostraciones deben usar únicamente archivos sintéticos.
- Los datos reales no deben copiarse a `tests/fixtures/`, logs, documentación,
  capturas, mensajes, commits ni salidas de depuración.
- Si se necesita un fixture versionado, debe generarse de forma sintética o
  anonimizarse y revisarse manualmente antes de añadirlo a Git.

Los archivos CSV y XLSX ubicados en `data/` están excluidos mediante
`.gitignore`. Esta exclusión reduce el riesgo de publicación accidental, pero
no sustituye los controles institucionales de acceso, cifrado y respaldo.

## Estado y continuidad

El estado técnico detallado, las decisiones vigentes y el procedimiento para
continuar se encuentran en `docs/HANDOFF_2026-10-08.md`. Los handoffs
anteriores se conservan como historial.
