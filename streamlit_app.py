"""Streamlit UI.

With API_URL set (Docker, Kubernetes) it calls the model server, so usage shows up in Grafana.
Without it (Streamlit Community Cloud, local) it scores in-process, training on first run.
"""

import os
import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mlapp.predictor import Predictor  # noqa: E402
from mlapp.train import METADATA_FILE, save, train  # noqa: E402

API_URL = os.environ.get("API_URL", "").rstrip("/")
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "artifacts"))
PRESETS = {
    "Dataset median": "median",
    "Typical benign": "median_benign",
    "Typical malignant": "median_malignant",
}


@st.cache_resource
def local_predictor():
    if not (MODEL_DIR / METADATA_FILE).exists():
        save(*train(), MODEL_DIR)
    return Predictor.load(MODEL_DIR)


@st.cache_data(ttl=60)
def remote_metadata():
    response = requests.get(f"{API_URL}/model", timeout=5)
    response.raise_for_status()
    return response.json()


def score(sample):
    if not API_URL:
        return local_predictor().predict(sample)
    response = requests.post(f"{API_URL}/predict", json={"features": sample}, timeout=5)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Tumor classifier", layout="wide")
st.title("Breast tumor classifier")
st.caption(
    "MLOps demo on the Wisconsin Diagnostic Breast Cancer dataset. Not a medical device: "
    "do not use it for diagnosis."
)

try:
    metadata = remote_metadata() if API_URL else local_predictor().metadata
except requests.RequestException as error:
    st.error(f"Could not reach the model API at {API_URL}: {error}")
    st.stop()

test_metrics = metadata["test_metrics"]
with st.sidebar:
    st.subheader("Model")
    st.write(f"**Version:** `{metadata['version']}`")
    st.write(f"**Type:** {metadata['model_type'].replace('_', ' ')}")
    st.write(f"**Serving:** {'model API' if API_URL else 'in-process'}")
    st.metric("Test ROC AUC", f"{test_metrics['roc_auc']:.3f}")
    st.metric("Test recall (malignant)", f"{test_metrics['recall']:.3f}")
    st.metric("Test precision", f"{test_metrics['precision']:.3f}")

preset = st.selectbox("Start from", list(PRESETS))
stats = metadata["feature_stats"]
sample = {}
groups = {
    "Mean": [f for f in metadata["features"] if f.startswith("mean ")],
    "Standard error": [f for f in metadata["features"] if f.endswith(" error")],
    "Worst": [f for f in metadata["features"] if f.startswith("worst ")],
}
for tab, features in zip(st.tabs(list(groups)), groups.values(), strict=True):
    with tab:
        columns = st.columns(2)
        for index, name in enumerate(features):
            low, high = stats[name]["min"], stats[name]["max"]
            sample[name] = columns[index % 2].slider(
                name,
                min_value=low,
                max_value=high,
                value=stats[name][PRESETS[preset]],
                step=(high - low) / 100,
                format="%.4f",
                key=f"{preset}:{name}",
            )

try:
    result = score(sample)
except requests.RequestException as error:
    st.error(f"Prediction failed: {error}")
    st.stop()

st.divider()
label_column, probability_column = st.columns(2)
label_column.metric("Prediction", result["label"].capitalize())
probability_column.metric("Probability malignant", f"{result['probability_malignant']:.1%}")
st.progress(result["probability_malignant"])
