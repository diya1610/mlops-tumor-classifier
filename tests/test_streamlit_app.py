from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "streamlit_app.py")


def run_app(monkeypatch, tmp_path):
    monkeypatch.delenv("API_URL", raising=False)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    return AppTest.from_file(APP, default_timeout=60).run()


def prediction(app):
    return next(metric.value for metric in app.metric if metric.label == "Prediction")


def test_presets_change_the_prediction(monkeypatch, tmp_path):
    app = run_app(monkeypatch, tmp_path)
    assert not app.exception

    app.selectbox[0].select("Typical malignant").run()
    assert prediction(app) == "Malignant"

    app.selectbox[0].select("Typical benign").run()
    assert prediction(app) == "Benign"
