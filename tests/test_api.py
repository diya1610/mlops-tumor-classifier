import pytest
from fastapi.testclient import TestClient

from mlapp.api import app
from mlapp.train import save, train


@pytest.fixture(scope="module")
def trained():
    return train()


@pytest.fixture(scope="module")
def client(trained, tmp_path_factory):
    model_dir = tmp_path_factory.mktemp("model")
    save(*trained, model_dir)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MODEL_DIR", str(model_dir))
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def sample(trained):
    metadata = trained[1]
    return {name: metadata["feature_stats"][name]["median"] for name in metadata["features"]}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_predict_returns_probability(client, sample):
    body = client.post("/predict", json={"features": sample}).json()
    assert body["label"] in {"benign", "malignant"}
    assert 0 <= body["probability_malignant"] <= 1
    assert 0.5 <= body["confidence"] <= 1


def test_predict_rejects_missing_feature(client, sample):
    del sample["mean radius"]
    response = client.post("/predict", json={"features": sample})
    assert response.status_code == 422
    assert response.json()["detail"]["missing_features"] == ["mean radius"]


def test_predict_rejects_unknown_feature(client, sample):
    response = client.post("/predict", json={"features": {**sample, "shoe size": 9}})
    assert response.status_code == 422
    assert response.json()["detail"]["unknown_features"] == ["shoe size"]


def test_predict_rejects_non_finite_value(client, sample):
    payload = '{"features": {"mean radius": NaN}}'
    response = client.post("/predict", content=payload)
    assert response.status_code == 422


def test_predict_flags_out_of_range_input(client, sample):
    sample["mean radius"] = 1e6
    body = client.post("/predict", json={"features": sample}).json()
    assert body["out_of_range_features"] == ["mean radius"]


def test_metrics_exposes_model_and_prediction_series(client, sample):
    client.post("/predict", json={"features": sample})
    client.get("/no/such/route")
    text = client.get("/metrics").text
    assert 'mlapi_requests_total{method="POST",path="/predict",status="200"}' in text
    assert 'path="unmatched"' in text
    assert "/no/such/route" not in text
    assert "mlapi_predictions_total" in text
    assert "mlapi_prediction_confidence_bucket" in text
    assert "mlapi_model_info" in text
    assert "mlapi_model_test_roc_auc" in text
