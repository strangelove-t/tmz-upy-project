# Checklist de QA UX/UI

Revisión con datos **sintéticos** únicamente (18 alumnos, 4 grupos, 13 casos),
en una copia temporal de la aplicación escuchando sólo en `127.0.0.1`. Las
capturas se revisaron y se eliminaron al terminar; no se usó el CSV real ni
`data/tamizaje.db`.

- Fecha: 2026-10-08
- Rama: `feature/local-access-pilot`
- Herramienta: Chromium sin interfaz (Playwright en un entorno temporal, no
  añadido al proyecto).

## A. Controles técnicos (equipo de desarrollo)

### Resoluciones (seis páginas)

- [x] 1366 × 768: sin texto cortado en títulos, métricas ni tablas.
- [x] 1920 × 1080: sin texto cortado en títulos, métricas ni tablas.
- [x] Sin scroll horizontal en la página ni dentro de las tablas, medido con
      `scrollWidth`/`clientWidth` en ambas resoluciones.
- [x] Jerarquía consistente: título, descripción breve y secciones en el mismo
      orden en las seis páginas.

### Estados

- [x] Sin base de datos: guía para importar desde Administración
      (pruebas `test_pages_without_database_show_guidance`).
- [x] Sin resultados para los filtros: mensaje con la acción a seguir
      (Casos y Estudiantes).
- [x] Operación correcta: “Seguimiento actualizado”, “Nota agregada”,
      “Importación completada” y confirmación de la ubicación del lote.
- [x] Error recuperable: contraseña incorrecta, CSV ilegible, mapeo inválido y
      fallo de importación o recálculo sin cambios parciales.
- [x] Bloqueo por confidencialidad: grupos con menos de 5 alumnos sin
      promedios, semáforos ni lista.
- [x] Bloqueo por autorización: importación real deshabilitada hasta marcar la
      casilla y escribir `IMPORTAR`; el modo de prueba nunca guarda.
- [x] Información sensible cerrada por defecto (interruptor apagado en
      Estudiantes › Respuestas).

### Navegación y teclado

- [x] Antes de la contraseña no se muestra el menú de páginas.
- [x] Orden del menú: Inicio, Casos, Estudiantes, Grupos, Reportes,
      Administración.
- [x] Con `Tab` se recorren menú, **Cerrar sesión** y contenido en orden.
- [x] Foco visible: contorno sólido de 3 px `#0B6E75` en enlaces, botones,
      pestañas y campos.
- [x] Los filtros de Casos se conservan al cambiar de página.
- [x] **Ver reportes del alumno** abre Reportes con el mismo alumno.

### Contraste (WCAG 2.1 AA)

- [x] Texto principal sobre fondo: 15.5:1.
- [x] Leyendas (`caption`) sobre fondo: 7.2:1 (se oscurecieron; antes 4.3:1).
- [x] Texto blanco sobre botón primario: 6.0:1.
- [x] Contorno de foco sobre fondo: 5.6:1.
- [x] Rojo y verde de semáforo sobre blanco: 5.6:1 y 5.1:1.
- [x] Todo semáforo se acompaña de texto (“Verde”, “Amarillo”, “Rojo”,
      “Incompleta” o “Pendiente de revisión”).

### Hallazgos corregidos durante la revisión

1. La barra lateral mostraba la lista automática de `pages/` en la pantalla de
   acceso.
2. Celdas vacías mostraban `None`.
3. La tabla de Casos y la de alertas necesitaban scroll horizontal.
4. Las métricas del caso seleccionado recortaban valores (“Atención …”).
5. El menú no mostraba contorno de foco con teclado.
6. Las leyendas no alcanzaban 4.5:1 de contraste.
7. El botón “Deploy” de Streamlit era visible para la usuaria.

### PDF y repositorio

- [x] PDF sintéticos de alumno y asesor renderizados con `pdftoppm` y revisados
      (estados verde, amarillo e incompleto).
- [x] Capturas, base sintética y copia temporal eliminadas.
- [x] `git ls-files data exports .streamlit/secrets.toml` sólo lista los
      `.gitkeep`.

### Limitaciones conocidas

- El botón del cargador de archivos dice “Upload” y “200MB per file”: es texto
  fijo de Streamlit y no se puede traducir sin componentes adicionales.
- Con `headless = true` el navegador no se abre solo; la guía de operación
  indica abrir `http://127.0.0.1:8501`.
- No hay identidad visual oficial de UPY; se usa una apariencia institucional
  neutra hasta contar con colores y logotipo autorizados.

## A2. Ajustes para una usuaria con poca experiencia tecnológica

Segunda ronda (2026-10-08, rama `feature/usabilidad-maestra`), revisada con la
misma metodología sintética y en el puerto aislado `127.0.0.1:8765`.

- [x] `run_windows.bat` abre el navegador solo (`--server.headless false`),
      muestra instrucciones en la ventana y hace pausa si falta `.venv`.
- [x] Botón **Salir de la aplicación**: cierra la sesión y apaga el servidor.
      Verificado en vivo: el puerto deja de responder.
- [x] Casos: un clic en cualquier celda abre el caso. La primera versión con
      casillas por fila resultó poco descubrible y se cambió.
- [x] Sí/No en lugar de casillas de sólo lectura.
- [x] Motivo de prioridad en lenguaje cotidiano.
- [x] Fechas `dd/mm/aaaa` en las vistas diarias (notas en hora local).
- [x] Sin versiones ni términos internos (scoring, envío, vigente, huella,
      None) en Inicio, Casos, Estudiantes, Grupos y Reportes; lo verifica
      `test_daily_pages_avoid_technical_jargon`.
- [x] Letra base de 18 px; las tablas siguen sin scroll horizontal a 1366 px.
- [x] Pestañas con aspecto de botón.
- [x] Explicaciones de Inicio visibles sin pasar el ratón.
- [x] Gráficas sin barra de zoom; tablas sin barra de descarga, búsqueda ni
      pantalla completa.

Pendiente: el selector de fecha muestra `dd/mm/yyyy` y el cargador dice
"Upload"; ambos textos son fijos de Streamlit.

## B. Aceptación institucional

Sólo la maestra marca estas casillas después de la revisión presencial.

- [ ] Desde Inicio identifica qué requiere atención y la siguiente acción.
- [ ] Registra un seguimiento completo en Casos sin ayuda.
- [ ] Encuentra el expediente de un alumno y descarga su reporte.
- [ ] Entiende el mensaje de confidencialidad de grupos pequeños.
- [ ] Aprueba el recorrido antes de procesar datos reales.

Observaciones: ____________________________________________

Nombre y firma: ______________________  Fecha: ____________
