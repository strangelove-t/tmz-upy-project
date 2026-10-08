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

1. Doble clic en `run_windows.bat` (o ejecutarlo en PowerShell).
2. La consola debe anunciar `http://127.0.0.1:8501`. Abre esa dirección en el
   navegador.
3. Escribe la contraseña y pulsa **Entrar**. La aplicación abre en **Inicio**,
   que muestra qué casos requieren atención.

La importación y el recálculo están en **Administración**, fuera del trabajo
diario. La importación real pide la autorización firmada, una casilla y
escribir `IMPORTAR`; el modo de prueba nunca guarda datos.

La aplicación sólo escucha en `127.0.0.1`: no acepta conexiones desde otras
computadoras. Si la consola muestra una dirección de red (`Network URL`) en
lugar de `127.0.0.1`, detén la aplicación y avisa a soporte.

## 3. Cerrar

1. Pulsa **Cerrar sesión** en la barra lateral.
2. Cierra la pestaña del navegador.
3. En la ventana de la consola presiona `Ctrl + C` y ciérrala.

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

- La generación por lote escribe en `exports\<fecha-hora>\` los PDFs y
  `manifiesto.csv`. Contienen información confidencial.
- Entrega los archivos sólo por los canales institucionales autorizados.
- Cuando termine el periodo institucional de conservación, elimina la carpeta
  del lote con la aplicación detenida:

```powershell
Remove-Item -Recurse "exports\<fecha-hora>"
```

## 7. Piloto con registros de prueba

Antes de la primera importación real, con exactamente un CSV en `data\`:

```powershell
.venv\Scripts\python.exe scripts\run_acceptance.py
```

Procesa sólo las líneas 2–15 en una base temporal que se borra al terminar y
muestra únicamente conteos. Resultado esperado: 14 envíos, 126 resultados de
área, 28 PDF validados y `Resultado: APROBADO`. Registra el resultado en
`docs\checklists\ACEPTACION_PILOTO.md`.

## 8. Reglas de seguridad

- Usa la aplicación sólo en la computadora institucional con disco cifrado.
- Conserva el CSV original en una ubicación restringida; no lo copies.
- No tomes capturas de pantalla con datos de estudiantes.
- La importación de las líneas 16 en adelante está **bloqueada** hasta que la
  maestra firme la autorización del checklist de aceptación.
