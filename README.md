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

## Ejecución

```bash
python -m streamlit run app.py
```

En Windows también se puede usar `run_windows.bat` después de preparar `.venv`.
La interfaz se abre en el navegador, pero el proceso y los datos permanecen en
la computadora local.

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

1. **Página principal**: selecciona el CSV exportado de Forms, revisa conteos y
   mapeo, desactiva el modo seguro, confirma la autorización e importa. El
   scoring, las alertas, las recomendaciones y los casos se calculan en la
   misma transacción.
2. **Resumen**: alumnos procesados, casos por nivel, solicitudes de contacto y
   distribución de semáforos por área.
3. **Casos**: lista priorizada con filtros y búsqueda. Selecciona un caso para
   registrar estado, contacto, responsable, próximo seguimiento, canalización,
   cierre y notas.
4. **Grupos**: promedios y semáforos por carrera y grupo. Los grupos con menos
   alumnos que `minimum_group_size` no muestran agregados ni datos individuales.
5. **Estudiantes**: expediente individual con áreas, recomendaciones, alertas,
   caso y respuestas (las sensibles quedan ocultas hasta activarlas). Si un
   alumno tiene varios envíos, aquí se elige el vigente.
6. **Reportes**: vista previa y descarga del reporte del estudiante o del
   expediente sanitizado para asesor; generación por lote en `exports/` con
   manifiesto `correo → archivo`. La fecha usa `report_timezone` y las celdas
   del manifiesto se protegen contra fórmulas de hojas de cálculo.

Al cambiar la versión activa de scoring o de reglas, usa **Recalcular** en la
página principal para aplicarla a los envíos ya guardados sin reimportar. Un
caso sin alertas vigentes conserva su historial, pero sale de la priorización.

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
continuar se encuentran en `docs/HANDOFF_2026-10-07.md`. El handoff anterior
(`docs/HANDOFF_2026-10-06.md`) se conserva como historial.
