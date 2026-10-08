# Tamizaje y Orientación UPY

Aplicación local para procesar por lote respuestas exportadas de Microsoft
Forms. El instrumento orienta el seguimiento institucional; no produce
diagnósticos psicológicos ni clínicos.

## Requisitos

- Python 3.12
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

## Piloto con registros de prueba

Con exactamente un CSV en `data/`:

```bash
python scripts/run_acceptance.py
```

Procesa sólo las líneas 2–15 en una base temporal y muestra únicamente
conteos. Los resultados se registran en `docs/checklists/ACEPTACION_PILOTO.md`;
la importación real permanece bloqueada hasta que la maestra firme la
autorización de ese checklist.

## Verificación

```bash
python -m pytest
python -m ruff check .
```

## Fuentes de verdad

El diccionario v1.2, el scoring v0.2, las 44 reglas de alerta v0.1 y las
recomendaciones por área y semáforo están disponibles en `config/`. Las
plantillas de reportes (lista blanca de campos) están en `templates/`. Consulta
`config/README.md` antes de cambiar una regla.

## Guía breve de uso

`run_windows.bat` abre el navegador automáticamente. Para terminar se usa el
botón **Salir de la aplicación**, que cierra la sesión y apaga el servidor.
Después de escribir la contraseña, el menú lateral muestra seis páginas,
ordenadas por frecuencia de uso:

1. **Inicio**: casos prioritarios, solicitudes de contacto, seguimientos
   vencidos, los siguientes cinco casos por atender y las áreas con más
   necesidad. Es el punto de partida diario.
2. **Casos**: lista priorizada con búsqueda y filtros (se conservan durante la
   sesión). Un clic en cualquier celda de una fila abre el caso, con pestañas
   *Motivo y alertas*, *Seguimiento* (contacto, estado, canalización y cierre)
   y *Notas*. El motivo de la prioridad se explica en lenguaje cotidiano.
3. **Estudiantes**: expediente con pestañas *Resultados* (nueve áreas,
   fortalezas, oportunidades y recomendaciones), *Seguimiento* y *Respuestas*
   (las sensibles quedan ocultas hasta activarlas). Si hay varios envíos, aquí
   se elige el vigente. **Ver reportes del alumno** abre Reportes con el mismo
   alumno.
4. **Grupos**: promedios y semáforos por carrera y grupo. Los grupos con menos
   alumnos que `minimum_group_size` no muestran agregados ni la lista.
5. **Reportes**: pestaña *Individual* con vista previa y descarga; pestaña
   *Por lote* con advertencia de confidencialidad, generación en `exports/` y
   manifiesto `correo → archivo`. La fecha usa `report_timezone` y las celdas
   del manifiesto se protegen contra fórmulas de hojas de cálculo.
6. **Administración**: importación en cuatro pasos (Archivo, Validación,
   Resumen, Confirmación). El modo de prueba está activo por defecto y nunca
   guarda datos; la importación real exige la autorización firmada, una casilla
   y escribir `IMPORTAR`. Aquí también está **Recalcular resultados**, que
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

En el archivo actualmente alojado en `data/`:

- La línea 1 contiene los encabezados.
- Las líneas 2 a 15 corresponden a 14 registros de prueba.
- Desde la línea 16 en adelante existen datos reales, sensibles y
  confidenciales.
- Sólo el encabezado y las líneas 2 a 15 pueden utilizarse durante el desarrollo
  y las pruebas locales.
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
