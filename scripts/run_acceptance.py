"""Ejecuta el piloto aislado con las líneas 2–15 del CSV local.

Uso (desde la raíz del proyecto):

    .venv\\Scripts\\python.exe scripts\\run_acceptance.py   (Windows)
    .venv/bin/python scripts/run_acceptance.py             (Linux/macOS)

Requiere exactamente un archivo ``*.csv`` en ``data/``. La base y los PDFs se
crean en un directorio temporal dentro de ``data/`` y se eliminan al terminar.
La salida sólo contiene conteos, rango de líneas, versiones y estados.
"""

import sys
from pathlib import Path

from tamizaje.acceptance import AcceptanceError, run_pilot

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> int:
    candidates = sorted(DATA_DIR.glob("*.csv"))
    if len(candidates) != 1:
        print(
            "Se requiere exactamente un archivo CSV en data/ "
            f"(encontrados: {len(candidates)})."
        )
        return 2

    try:
        result = run_pilot("piloto.csv", candidates[0].read_bytes(), DATA_DIR)
    except AcceptanceError as error:
        print(f"Piloto no aprobado: {error}")
        return 1
    except Exception as error:  # Nunca imprimir el mensaje original.
        # Podría contener valores del archivo.
        print(f"Piloto no aprobado: error interno ({type(error).__name__}).")
        return 1

    print("Piloto aislado (sólo registros de prueba)")
    print(f"Líneas: {result.source_lines[0]}–{result.source_lines[1]}")
    print(f"Envíos procesados: {result.submissions}")
    print(
        f"Resultados de área: {result.area_results} "
        f"({result.complete_area_results} completos)"
    )
    print(f"Alertas: {result.alert_count} · Casos activos: {result.case_count}")
    print(f"Envíos recalculados: {result.recalculated}")
    print(f"PDF validados: {result.pdf_count}")
    print(
        f"Versiones: cuestionario {result.questionnaire_version} · "
        f"scoring {result.scoring_version} · reglas {result.rule_version}"
    )
    print(
        "Temporales eliminados: "
        + ("sí" if result.temporary_files_removed else "NO")
    )
    print("Resultado: " + ("APROBADO" if result.passed else "NO APROBADO"))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
