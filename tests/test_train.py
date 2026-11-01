import pytest

from mlapp.predictor import Predictor
from mlapp.train import save, train


def test_training_passes_gate_and_records_version(monkeypatch):
    monkeypatch.setenv("MODEL_VERSION", "abc1234")
    _, metadata = train()
    assert metadata["version"] == "abc1234"
    assert metadata["test_metrics"]["roc_auc"] >= 0.95
    assert metadata["test_metrics"]["recall"] >= 0.90
    assert len(metadata["features"]) == 30


def test_quality_gate_rejects_weak_model():
    with pytest.raises(ValueError, match="Quality gate failed"):
        train(min_auc=1.1)


def test_saved_model_separates_typical_samples(tmp_path):
    save(*train(), tmp_path)
    predictor = Predictor.load(tmp_path)
    stats = predictor.metadata["feature_stats"]

    benign = {name: stats[name]["median_benign"] for name in predictor.features}
    malignant = {name: stats[name]["median_malignant"] for name in predictor.features}

    assert predictor.predict(benign)["label"] == "benign"
    assert predictor.predict(malignant)["label"] == "malignant"
    assert predictor.predict(benign)["out_of_range_features"] == []
