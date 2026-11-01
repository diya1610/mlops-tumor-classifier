"""Load a trained model and score a single sample."""

import json
from pathlib import Path

import joblib
import pandas as pd

from mlapp.train import METADATA_FILE, MODEL_FILE


class Predictor:
    def __init__(self, model, metadata):
        self.model = model
        self.metadata = metadata
        self.features = metadata["features"]

    @classmethod
    def load(cls, model_dir):
        model_dir = Path(model_dir)
        metadata = json.loads((model_dir / METADATA_FILE).read_text())
        return cls(joblib.load(model_dir / MODEL_FILE), metadata)

    def out_of_range(self, sample):
        """Names of features outside the range seen in training, a simple drift signal."""
        stats = self.metadata["feature_stats"]
        return [
            name
            for name in self.features
            if not stats[name]["min"] <= sample[name] <= stats[name]["max"]
        ]

    def predict(self, sample):
        frame = pd.DataFrame([[sample[name] for name in self.features]], columns=self.features)
        malignant = float(self.model.predict_proba(frame)[0, 1])
        label = "malignant" if malignant >= 0.5 else "benign"
        return {
            "label": label,
            "probability_malignant": malignant,
            "confidence": max(malignant, 1 - malignant),
            "out_of_range_features": self.out_of_range(sample),
            "model_version": self.metadata["version"],
        }
