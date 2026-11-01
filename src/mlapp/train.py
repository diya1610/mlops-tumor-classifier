"""Train candidate models, keep the best, and refuse to ship one below the quality gate.

Usage: python -m mlapp.train --output artifacts
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42
MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"


def load_data():
    """Return features and a target where 1 means malignant (sklearn encodes it as 0)."""
    dataset = load_breast_cancer(as_frame=True)
    return dataset.data, 1 - dataset.target


def candidates():
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, random_state=SEED)
        ),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=SEED),
    }


def model_version():
    """Tie the model to the commit that built it. Docker builds have no .git, so use the env."""
    if version := os.environ.get("MODEL_VERSION"):
        return version
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "dev"


def train(min_auc=0.95, min_recall=0.90):
    """Return (model, metadata). Raises ValueError when the best model misses the gate."""
    X, y = load_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=SEED
    )

    cv_auc = {
        name: float(cross_val_score(model, X_train, y_train, cv=5, scoring="roc_auc").mean())
        for name, model in candidates().items()
    }
    best_name = max(cv_auc, key=cv_auc.get)
    model = candidates()[best_name].fit(X_train, y_train)

    predicted = model.predict(X_test)
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])),
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted)),
        "recall": float(recall_score(y_test, predicted)),
    }
    if metrics["roc_auc"] < min_auc or metrics["recall"] < min_recall:
        raise ValueError(
            f"Quality gate failed: {metrics} (need roc_auc>={min_auc}, recall>={min_recall})"
        )

    metadata = {
        "version": model_version(),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_type": best_name,
        "cv_roc_auc": cv_auc,
        "test_metrics": metrics,
        "features": list(X.columns),
        "feature_stats": {
            column: {
                "min": float(X_train[column].min()),
                "max": float(X_train[column].max()),
                "median": float(X_train[column].median()),
                "median_benign": float(X_train.loc[y_train == 0, column].median()),
                "median_malignant": float(X_train.loc[y_train == 1, column].median()),
            }
            for column in X.columns
        },
    }
    return model, metadata


def save(model, metadata, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output / MODEL_FILE)
    (output / METADATA_FILE).write_text(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--min-auc", type=float, default=0.95)
    parser.add_argument("--min-recall", type=float, default=0.90)
    args = parser.parse_args()

    try:
        model, metadata = train(args.min_auc, args.min_recall)
    except ValueError as error:
        sys.exit(str(error))
    save(model, metadata, args.output)
    print(f"Saved {metadata['model_type']} to {args.output}: {metadata['test_metrics']}")


if __name__ == "__main__":
    main()
