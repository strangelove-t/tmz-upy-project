# Acceso local y piloto operativo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restringir la aplicación a una contraseña local en `127.0.0.1` y ejecutar una aceptación auditable que importe únicamente los 14 registros de prueba en una base temporal.

**Architecture:** La autenticación usa sólo biblioteca estándar (`hashlib.scrypt`, `hmac` y `secrets`) y un único hash local en Streamlit Secrets. La aceptación reconstruye en memoria un CSV con encabezado y las primeras 14 filas, lo procesa en una base temporal y emite únicamente métricas no sensibles; nunca abre la importación real ni escribe en `data/tamizaje.db`.

**Tech Stack:** Python 3.12, Streamlit, SQLite, pytest, stdlib `hashlib`, `hmac`, `getpass`, `csv` y `tempfile`.

---

### Task 1: Primitivas de contraseña

**Files:**
- Create: `src/tamizaje/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing password tests**

```python
import pytest

from tamizaje.auth import hash_password, verify_password


def test_password_hash_round_trip_without_plaintext() -> None:
    encoded = hash_password("frase-segura-de-prueba", salt=bytes(range(16)))

    assert "frase-segura-de-prueba" not in encoded
    assert verify_password("frase-segura-de-prueba", encoded)
    assert not verify_password("incorrecta", encoded)


def test_password_rejects_short_value_and_malformed_hash() -> None:
    with pytest.raises(ValueError, match="12 caracteres"):
        hash_password("corta")
    assert not verify_password("cualquier-clave", "valor-inválido")
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: FAIL con `ModuleNotFoundError: tamizaje.auth`.

- [ ] **Step 3: Implement the minimal scrypt format**

Implementar un formato autocontenido `scrypt$n$r$p$salt_hex$digest_hex`:

```python
import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2**14, 8, 1, 32


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN
    )
    return f"scrypt${N}${R}${P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (N, R, P):
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(expected)),
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError, MemoryError):
        return False
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/tamizaje/auth.py tests/test_auth.py
git commit -m "feat: add local password hashing"
```

### Task 2: Configuración local y generación del secreto

**Files:**
- Create: `.streamlit/config.toml`
- Create: `.streamlit/secrets.example.toml`
- Create: `scripts/set_local_password.py`
- Modify: `.gitignore`
- Modify: `run_windows.bat`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing secret-file test**

```python
from scripts.set_local_password import write_secret


def test_write_secret_stores_only_verifiable_hash(tmp_path) -> None:
    target = tmp_path / "secrets.toml"
    write_secret(target, "frase-segura-de-prueba")

    content = target.read_text(encoding="utf-8")
    assert "frase-segura-de-prueba" not in content
    encoded = content.split('password_hash = "', 1)[1].split('"', 1)[0]
    assert verify_password("frase-segura-de-prueba", encoded)
```

- [ ] **Step 2: Run the test to verify RED**

Run: `.venv/bin/pytest tests/test_auth.py::test_write_secret_stores_only_verifiable_hash -v`
Expected: FAIL porque `scripts.set_local_password` no existe.

- [ ] **Step 3: Add localhost configuration and ignored secret**

`.streamlit/config.toml`:

```toml
[server]
address = "127.0.0.1"
headless = true

[browser]
gatherUsageStats = false
```

`.streamlit/secrets.example.toml`:

```toml
[auth]
password_hash = "GENERAR_CON_scripts/set_local_password.py"
```

Añadir `.streamlit/secrets.toml` a `.gitignore`. En `run_windows.bat`, ejecutar
Streamlit también con `--server.address 127.0.0.1` para que el límite sea
explícito incluso si existe configuración global del usuario.

- [ ] **Step 4: Implement local secret generation**

El script usará `getpass.getpass()` dos veces, rechazará diferencias y escribirá
mediante una función comprobable:

```python
def write_secret(path: Path, password: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = hash_password(password)
    path.write_text(f'[auth]\npassword_hash = "{encoded}"\n', encoding="utf-8")
    path.chmod(0o600)
```

No imprimirá la contraseña ni el hash; sólo confirmará la ruta creada.

- [ ] **Step 5: Run tests and inspect tracked files**

Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: all passed.

Run: `git check-ignore .streamlit/secrets.toml`
Expected: `.streamlit/secrets.toml`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .streamlit/config.toml .streamlit/secrets.example.toml scripts/set_local_password.py run_windows.bat tests/test_auth.py
git commit -m "feat: configure local-only application secret"
```

### Task 3: Puerta de acceso Streamlit

**Files:**
- Modify: `src/tamizaje/ui.py`
- Modify: `app.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing UI tests**

Crear un helper de `AppTest` que asigne un hash sintético a `app.secrets` antes
de ejecutar. Cubrir estos comportamientos:

```python
def test_app_requires_password() -> None:
    app = configured_app("app.py").run()
    assert any(field.label == "Contraseña" for field in app.text_input)
    assert not app.get("file_uploader")


def test_app_rejects_wrong_password_and_accepts_correct_one() -> None:
    app = configured_app("app.py").run()
    next(field for field in app.text_input if field.label == "Contraseña").input(
        "incorrecta"
    )
    next(button for button in app.button if button.label == "Entrar").click().run()
    assert app.error

    next(field for field in app.text_input if field.label == "Contraseña").input(
        TEST_PASSWORD
    )
    next(button for button in app.button if button.label == "Entrar").click().run()
    assert app.get("file_uploader")
```

En las pruebas existentes, establecer `app.session_state["authenticated"] = True`
antes de `run()` para conservar su propósito actual. Añadir una prueba de página
que confirme que, sin sesión autenticada, no aparece ningún dataframe.

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_app.py tests/test_pages.py -v`
Expected: FAIL porque la aplicación aún no solicita contraseña.

- [ ] **Step 3: Implement the gate once in `ui.py`**

```python
def require_authentication() -> None:
    if st.session_state.get("authenticated"):
        if st.sidebar.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()
        return
    try:
        password_hash = st.secrets["auth"]["password_hash"]
    except (KeyError, FileNotFoundError):
        st.error("La aplicación no tiene una contraseña local configurada.")
        st.stop()
    with st.form("login"):
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
    if submitted and verify_password(password, str(password_hash)):
        st.session_state["authenticated"] = True
        st.rerun()
    if submitted:
        st.error("Contraseña incorrecta.")
    st.stop()
```

Llamar a `require_authentication()` inmediatamente después de
`st.set_page_config()` en `app.py`. Llamarlo al inicio de `require_context()`
para cubrir las cinco páginas sin duplicar lógica.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_app.py tests/test_pages.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add app.py src/tamizaje/ui.py tests/test_app.py tests/test_pages.py
git commit -m "feat: require local application password"
```

### Task 4: Aceptación aislada de las líneas 2–15

**Files:**
- Create: `src/tamizaje/acceptance.py`
- Create: `scripts/run_acceptance.py`
- Create: `tests/test_acceptance.py`

- [ ] **Step 1: Write the failing slice test**

Construir un CSV sintético de 20 registros y comprobar que la función devuelve
un `CsvPreview` importable con exactamente las líneas permitidas:

```python
def test_test_only_preview_contains_header_and_first_14_rows() -> None:
    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [{} for _ in range(20)])

    preview = test_only_preview("local.csv", content, questionnaire)

    assert preview.row_count == 14
    assert preview.source_row_numbers == tuple(range(2, 16))
    assert not preview.is_limited
    assert preview.mapping.is_valid
```

- [ ] **Step 2: Run the slice test to verify RED**

Run: `.venv/bin/pytest tests/test_acceptance.py::test_test_only_preview_contains_header_and_first_14_rows -v`
Expected: FAIL porque `tamizaje.acceptance` no existe.

- [ ] **Step 3: Implement safe reconstruction**

`test_only_preview` detectará encoding y delimitador, leerá con `csv.reader`,
tomará encabezado y exactamente 14 registros con `islice`, reescribirá sólo
esas filas a `io.StringIO` y llamará `preview_csv` sin `max_rows`. Si hay menos
de 14 registros, fallará con `AcceptanceError` sin incluir valores del archivo.

- [ ] **Step 4: Write the failing isolated-pilot test**

```python
def test_run_pilot_imports_only_test_rows_into_temporary_database(tmp_path) -> None:
    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [{} for _ in range(20)])

    result = run_pilot("local.csv", content, tmp_path)

    assert result.submissions == 14
    assert result.source_lines == (2, 15)
    assert result.area_results == 14 * 9
    assert result.pdf_count == 14 * 2
    assert not (tmp_path / "tamizaje.db").exists()
    assert "synthetic" not in repr(result).lower()
```

- [ ] **Step 5: Run the pilot test to verify RED**

Run: `.venv/bin/pytest tests/test_acceptance.py::test_run_pilot_imports_only_test_rows_into_temporary_database -v`
Expected: FAIL porque `run_pilot` no existe.

- [ ] **Step 6: Implement the temporary pilot**

`run_pilot` usará `TemporaryDirectory(dir=workspace)` para crear SQLite y PDFs,
ejecutará `import_preview`, `recalculate_all` y `generate_report`, comprobará
cabecera y cierre `%PDF`, y devolverá únicamente una dataclass con conteos,
rango de líneas, versiones y resultado booleano. El contexto temporal eliminará
base y PDFs antes de retornar. No devolverá nombres, correos ni respuestas.

El comando `scripts/run_acceptance.py` exigirá exactamente un `*.csv` en
`data/`, llamará al piloto y mostrará sólo las métricas aprobadas. Cero o varios
archivos producirán un error seguro sin listar nombres.

- [ ] **Step 7: Run acceptance tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_acceptance.py -v`
Expected: all passed.

- [ ] **Step 8: Commit**

```bash
git add src/tamizaje/acceptance.py scripts/run_acceptance.py tests/test_acceptance.py
git commit -m "test: add isolated pilot acceptance runner"
```

### Task 5: Operación, respaldo y autorización institucional

**Files:**
- Create: `docs/OPERACION_LOCAL.md`
- Create: `docs/checklists/ACEPTACION_PILOTO.md`
- Modify: `README.md`
- Modify: `docs/HANDOFF_2026-10-07.md`

- [ ] **Step 1: Write the local operating guide**

Documentar comandos exactos de Windows para:

1. crear/cambiar contraseña con
   `.venv\Scripts\python.exe scripts\set_local_password.py`;
2. iniciar con `run_windows.bat` y confirmar URL `127.0.0.1`;
3. detener Streamlit antes de respaldar;
4. copiar `data\tamizaje.db` a almacenamiento institucional cifrado;
5. restaurar sólo con la aplicación detenida y conservando una copia anterior;
6. eliminar PDFs cuando termine su periodo institucional de conservación;
7. bloquear Windows y evitar sincronización con cuentas personales.

- [ ] **Step 2: Create the acceptance checklist**

Incluir casillas para acceso, rechazo de contraseña, sesión, 14 filas, mapeo,
scoring, alertas, casos, recálculo, grupos, PDFs, respaldo/restauración y revisión
institucional de los cinco contenidos pendientes. La última casilla será:

```markdown
- [ ] La maestra autoriza por escrito procesar las líneas 16 en adelante.
```

Mientras permanezca vacía, el documento indicará “Importación real bloqueada”.

- [ ] **Step 3: Update entry-point documentation**

README y handoff enlazarán la guía y el checklist, explicarán que no hay perfiles
y dejarán explícito que desarrollo no necesita una identidad dentro de la app.

- [ ] **Step 4: Check documentation and commit**

Run: `git diff --check`
Expected: exit code 0.

```bash
git add README.md docs/HANDOFF_2026-10-07.md docs/OPERACION_LOCAL.md docs/checklists/ACEPTACION_PILOTO.md
git commit -m "docs: add local operation and pilot checklist"
```

### Task 6: Ejecución del piloto y verificación final

**Files:**
- Modify: `docs/checklists/ACEPTACION_PILOTO.md` únicamente para marcar checks comprobados automáticamente, sin datos personales.

- [ ] **Step 1: Generate the local secret outside Git**

Run interactively on the installation machine:
`.venv/bin/python scripts/set_local_password.py`
Expected: `.streamlit/secrets.toml` creado e ignorado. Durante desarrollo se
usará una contraseña sintética temporal; la maestra establecerá la definitiva
directamente en su computadora.

- [ ] **Step 2: Run the actual test-only pilot**

Run: `.venv/bin/python scripts/run_acceptance.py`
Expected: 14 envíos, líneas 2–15, 126 resultados de área, 28 PDFs validados y
cero archivos temporales persistentes. La salida no debe contener nombres,
correos ni respuestas.

- [ ] **Step 3: Verify localhost binding**

Run: `.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.headless true`
Expected: la consola anuncia `http://127.0.0.1:8501`; una conexión a la IP de red
del equipo no debe estar escuchando.

- [ ] **Step 4: Run complete verification**

Run: `.venv/bin/pytest -v`
Expected: all tests passed.

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`.

Run: `.venv/bin/python -m compileall -q src tests scripts app.py pages`
Expected: exit code 0.

Run: `git ls-files data exports .streamlit/secrets.toml`
Expected: sólo `data/.gitkeep` y `exports/.gitkeep`; nunca el secreto ni datos.

- [ ] **Step 5: Render and inspect synthetic PDFs**

Generar reportes con `tests/synthetic_forms.py`, renderizarlos con `pdftoppm`,
inspeccionar todas las páginas y eliminar el directorio temporal después.

- [ ] **Step 6: Record verified checklist items and commit**

Marcar sólo controles demostrados por comandos. Mantener sin marcar la revisión
de la maestra y la autorización de datos reales.

```bash
git add docs/checklists/ACEPTACION_PILOTO.md
git commit -m "docs: record pilot acceptance evidence"
```
