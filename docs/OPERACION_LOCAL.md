# Operación local de Tamizaje UPY

Guía para la computadora institucional donde se usa la aplicación. Todos los
comandos se ejecutan en PowerShell desde la carpeta del proyecto.

La aplicación tiene **una sola contraseña** y no usa usuarios, perfiles ni
roles. El equipo de desarrollo da soporte sobre el código y no necesita otra
identidad dentro de la aplicación instalada.

## 1. Crear o cambiar la contraseña

```powershell
.venv\Scripts\python.exe scripts\set_local_password.py
```

- Pide la contraseña dos veces (mínimo 12 caracteres) y no la muestra.
- Guarda sólo sal y hash `scrypt` en `.streamlit\secrets.toml`, que Git ignora.
- La contraseña definitiva la establece la maestra directamente en su equipo.
- Para cambiarla se ejecuta el mismo comando; después se reinicia la
  aplicación. No existe recuperación: si se olvida, se crea una nueva.

## 2. Iniciar

1. Doble clic en el acceso directo **Tamizaje UPY** del escritorio (o en
   `run_windows.bat`).
2. Se abre una ventana negra titulada *Tamizaje UPY - no cierres esta ventana*
   y, unos segundos después, el navegador con la aplicación. No cierres la
   ventana negra; puedes minimizarla.
3. Escribe la contraseña y pulsa **Entrar**. La aplicación abre en **Inicio**,
   que muestra qué casos requieren atención.

Si el navegador no se abre solo, escribe `http://127.0.0.1:8501` en la barra de
direcciones.

La importación y el recálculo están en **Administración**, fuera del trabajo
diario. Al cargar un CSV, la aplicación valida todas las respuestas desde la
línea 2 sin guardarlas. Para importar pide autorización escrita, una casilla y
escribir `IMPORTAR`.

La aplicación sólo escucha en `127.0.0.1`: no acepta conexiones desde otras
computadoras. Si la consola muestra una dirección de red (`Network URL`) en
lugar de `127.0.0.1`, detén la aplicación y avisa a soporte.

### Crear el acceso directo (una sola vez, soporte)

1. Clic derecho sobre `run_windows.bat` › **Mostrar más opciones** ›
   **Enviar a** › **Escritorio (crear acceso directo)**.
2. Renombra el acceso directo del escritorio como **Tamizaje UPY**.
3. Opcional: clic derecho › **Propiedades** › **Ejecutar: Minimizada**, para
   que la ventana negra no estorbe.

## 3. Cerrar

1. Pulsa **Salir de la aplicación** (botón verde del menú izquierdo). Cierra la
   sesión y apaga la aplicación; la ventana negra se cierra sola.
2. Cierra la pestaña del navegador. Si aparece un aviso de conexión, es normal.

**Cerrar sesión** sólo pide de nuevo la contraseña, sin apagar la aplicación.
Recargar la página (`F5`) también cierra la sesión.

Bloquea Windows (`Windows + L`) siempre que te alejes del equipo, aunque la
aplicación esté cerrada.

## 4. Respaldar la base

La base está en `data\tamizaje.db`. **Detén la aplicación antes de copiarla.**

```powershell
$fecha = Get-Date -Format "yyyyMMdd-HHmm"
Copy-Item data\tamizaje.db "<RUTA_INSTITUCIONAL_CIFRADA>\tamizaje-$fecha.db"
```

- Usa únicamente almacenamiento institucional autorizado y cifrado.
- Nunca copies la base a USB personales, correo o servicios de sincronización
  personales (OneDrive/Google Drive personales, etc.).

## 5. Restaurar una copia

Con la aplicación detenida:

```powershell
$fecha = Get-Date -Format "yyyyMMdd-HHmm"
Move-Item data\tamizaje.db "data\tamizaje-antes-de-restaurar-$fecha.db"
Copy-Item "<RUTA_INSTITUCIONAL_CIFRADA>\tamizaje-AAAAMMDD-HHMM.db" data\tamizaje.db
```

Inicia la aplicación y verifica Inicio y Casos. Conserva la copia anterior
hasta confirmar que la restauración es correcta; después elimínala.

## 6. Reportes exportados

- El **Reporte del alumno** nunca incluye diagnósticos ni condiciones de salud.
- El **Expediente para tutor** excluye esa información por defecto. La casilla
  para incluirla debe activarse conscientemente para cada alumno o lote y
  muestra una advertencia antes de generar el PDF. Incluye las nueve áreas con
  puntaje, semáforo, interpretación y sugerencia para tutoría.
- El **Resumen grupal** está en *Reportes › Grupal*: elige carrera y grupo y
  descarga el PDF para el tutor del grupo. Explica las nueve áreas, semáforos y
  niveles de atención; lista sólo alumnos con atención abierta en el mismo orden
  que **Casos**. De cada alumno muestra nombre, nivel, número de alertas y si
  pidió contacto. No incluye correos, respuestas, motivos, notas ni diagnósticos.
  No se habilita si el grupo tiene menos de `minimum_group_size` alumnos.
- El resumen grupal se genera en memoria, no se guarda automáticamente en
  `exports/` ni se envía por correo. **Contiene nombres**: entrégalo únicamente
  al tutor del grupo por un canal institucional autorizado y consérvalo sólo
  el tiempo necesario. Los PDF individuales llevan el nombre completo del
  alumno en el nombre de archivo; los grupales llevan el grupo.
- En lotes sensibles se requiere una segunda confirmación. La auditoría registra
  si el archivo incluyó la síntesis, pero no copia diagnósticos al registro.
- La generación por lote escribe en `exports\<fecha-hora>\` los PDFs y
  `manifiesto.csv`. Contienen información confidencial.
- Entrega los archivos sólo por los canales institucionales autorizados.
- Cuando termine el periodo institucional de conservación, elimina la carpeta
  del lote con la aplicación detenida:

```powershell
Remove-Item -Recurse "exports\<fecha-hora>"
```

## 7. Piloto histórico de soporte

El script siguiente es exclusivo del antiguo archivo con 14 filas de prueba;
no forma parte del uso normal y no debe ejecutarse con la exportación actual:

```powershell
.venv\Scripts\python.exe scripts\run_acceptance.py
```

Ese script procesa las líneas 2–15 en una base temporal. En el archivo actual
esas líneas contienen datos reales. Para verificar un CSV actual, usa la
previsualización de **Administración**, que analiza desde la línea 2 y no
guarda nada hasta completar la confirmación.

## 8. Reglas de seguridad

- Usa la aplicación sólo en la computadora institucional con disco cifrado.
- Conserva el CSV original en una ubicación restringida; no lo copies.
- No tomes capturas de pantalla con datos de estudiantes.
- La base local puede contener importaciones anteriores. Si un archivo completo
  o algún identificador ya fue importado, la aplicación rechaza el lote sin
  guardar cambios parciales.
- La evidencia de autorización del checklist sigue pendiente de conciliación
  documental. Hasta resolverla, no realices nuevas importaciones ni compartas
  nuevos reportes fuera de la computadora institucional.
