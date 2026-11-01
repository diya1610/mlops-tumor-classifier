"""Generate the Grafana dashboard JSON: python scripts/build_dashboard.py"""

import json
from pathlib import Path

OUTPUT = Path(__file__).parent.parent / "k8s/monitoring/ml-api-dashboard.json"
DATASOURCE = {"type": "prometheus", "uid": "prometheus"}
# Series colors are fixed per entity, so a class keeps its color whichever series is present.
BENIGN = "#2a78d6"
MALIGNANT = "#eb6834"


def target(expr, legend="__auto", instant=False):
    return {
        "datasource": DATASOURCE,
        "expr": expr,
        "legendFormat": legend,
        "refId": "A",
        "instant": instant,
        "range": not instant,
    }


def stat(panel_id, title, expr, x, unit="none", legend="", text_mode="value", decimals=None):
    defaults = {"unit": unit, "color": {"mode": "fixed", "fixedColor": "text"}}
    if decimals is not None:
        defaults["decimals"] = decimals
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "datasource": DATASOURCE,
        "gridPos": {"x": x, "y": 0, "w": 6, "h": 4},
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "colorMode": "none",
            "graphMode": "none",
            "textMode": text_mode,
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "targets": [target(expr, legend or "__auto", instant=True)],
    }


def series(panel_id, title, expr, x, y, unit, legend, description, overrides=(), **custom):
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "gridPos": {"x": x, "y": y, "w": 12, "h": 8},
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": 0,
                # Without a cap, an all-zero ratio gets an axis running up to 10000%.
                **({"max": 1} if unit == "percentunit" else {}),
                "custom": {"lineWidth": 2, "fillOpacity": 0, "showPoints": "never", **custom},
            },
            "overrides": list(overrides),
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [target(expr, legend)],
    }


def fixed_color(name, color):
    return {
        "matcher": {"id": "byName", "options": name},
        "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}],
    }


PANELS = [
    stat(
        1,
        "Model version",
        # One tile per distinct model, however many pods serve it.
        "max by (version, model_type) (mlapi_model_info)",
        0,
        legend="{{version}} ({{model_type}})",
        text_mode="name",
    ),
    stat(2, "Test ROC AUC", "max(mlapi_model_test_roc_auc)", 6, decimals=3),
    stat(3, "API instances up", 'sum(up{job="api"})', 12, decimals=0),
    stat(
        4,
        "Requests with 5xx, last 1h",
        'sum(increase(mlapi_requests_total{status=~"5.."}[1h])) or vector(0)',
        18,
        decimals=0,
    ),
    series(
        5,
        "Request rate",
        'sum by (path) (rate(mlapi_requests_total{path!~"/metrics|/health"}[5m]))',
        0,
        4,
        "reqps",
        "{{path}}",
        "Requests per second by route, excluding scrapes and health probes.",
    ),
    series(
        6,
        "/predict latency",
        "histogram_quantile(0.95, sum by (le) "
        '(rate(mlapi_request_duration_seconds_bucket{path="/predict"}[5m])))',
        12,
        4,
        "s",
        "p95",
        "95th percentile. The HighPredictLatency alert fires above 0.5 s.",
    ),
    series(
        7,
        "Error ratio",
        'sum(rate(mlapi_requests_total{status=~"5.."}[5m])) '
        "/ sum(rate(mlapi_requests_total[5m])) or vector(0)",
        0,
        12,
        "percentunit",
        "5xx share",
        "Share of requests failing. The HighErrorRate alert fires above 5%.",
    ),
    series(
        8,
        "Predictions by class",
        "sum by (label) (rate(mlapi_predictions_total[5m]))",
        12,
        12,
        "reqps",
        "{{label}}",
        "A shift in the class mix can signal drift in the incoming data.",
        overrides=[fixed_color("benign", BENIGN), fixed_color("malignant", MALIGNANT)],
    ),
    series(
        9,
        "Median prediction confidence",
        "histogram_quantile(0.5, sum by (le) (rate(mlapi_prediction_confidence_bucket[5m])))",
        0,
        20,
        "percentunit",
        "median",
        "Probability of the predicted class. A falling trend means less certain predictions.",
    ),
    series(
        10,
        "Out-of-range inputs",
        "sum(rate(mlapi_out_of_range_predictions_total[5m])) "
        "/ sum(rate(mlapi_predictions_total[5m]))",
        12,
        20,
        "percentunit",
        "share of predictions",
        "Inputs with a feature outside the training range. The InputDrift alert fires above 20%.",
    ),
]

DASHBOARD = {
    "uid": "ml-api",
    "title": "ML API",
    "tags": ["mlops"],
    "schemaVersion": 39,
    "refresh": "30s",
    "time": {"from": "now-1h", "to": "now"},
    "panels": PANELS,
}

if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(DASHBOARD, indent=2) + "\n")
