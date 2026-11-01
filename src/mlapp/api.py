"""FastAPI model server exposing predictions and Prometheus metrics."""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, FiniteFloat

from mlapp.predictor import Predictor

REQUESTS = Counter("mlapi_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("mlapi_request_duration_seconds", "HTTP request latency", ["path"])
PREDICTIONS = Counter("mlapi_predictions_total", "Predictions by class", ["label"])
CONFIDENCE = Histogram(
    "mlapi_prediction_confidence",
    "Probability of the predicted class",
    buckets=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)
OUT_OF_RANGE = Counter(
    "mlapi_out_of_range_predictions_total",
    "Predictions with at least one feature outside the training range",
)
MODEL_INFO = Gauge("mlapi_model_info", "Loaded model", ["version", "model_type"])
MODEL_AUC = Gauge("mlapi_model_test_roc_auc", "Test ROC AUC recorded at training time")


@asynccontextmanager
async def lifespan(app: FastAPI):
    predictor = Predictor.load(os.environ.get("MODEL_DIR", "artifacts"))
    app.state.predictor = predictor
    metadata = predictor.metadata
    MODEL_INFO.labels(metadata["version"], metadata["model_type"]).set(1)
    MODEL_AUC.set(metadata["test_metrics"]["roc_auc"])
    yield


app = FastAPI(title="Tumor classifier API", lifespan=lifespan)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # Label by route template so arbitrary URLs cannot create unbounded metric series.
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(path).observe(time.perf_counter() - start)


class PredictRequest(BaseModel):
    features: dict[str, FiniteFloat]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model")
def model(request: Request):
    return request.app.state.predictor.metadata


@app.post("/predict")
def predict(body: PredictRequest, request: Request):
    predictor = request.app.state.predictor
    missing = sorted(set(predictor.features) - set(body.features))
    unknown = sorted(set(body.features) - set(predictor.features))
    if missing or unknown:
        raise HTTPException(422, {"missing_features": missing, "unknown_features": unknown})

    result = predictor.predict(body.features)
    PREDICTIONS.labels(result["label"]).inc()
    CONFIDENCE.observe(result["confidence"])
    if result["out_of_range_features"]:
        OUT_OF_RANGE.inc()
    return result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
