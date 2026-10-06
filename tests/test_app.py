from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_shows_csv_import_control() -> None:
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 1
    assert any(
        "Catálogo aprobado: 105" in caption.value
        and "Texto verificado: 0" in caption.value
        and "Pendientes de revisión: 0" in caption.value
        for caption in app.caption
    )
    assert any(
        "Las líneas 2–15 se excluyen de la importación real" in info.value
        for info in app.info
    )
    assert any("Scoring activo: 0.2" in caption.value for caption in app.caption)
