# ml_sites.py
from pathlib import Path
import joblib
import numpy as np

MODEL_PATH = Path("data/site_model.joblib")

FEATURE_ORDER = [
    "humidity",        # %
    "temperature",     # °C
    "wind_speed",      # m/s
    "ndvi",            # 0..1
    "lst_night_c",     # °C (cooler = better)
    "dist_coast_km",   # km (closer = better)
    "pm25_mean"        # µg/m³ (lower = better)
]

def load_site_model():
    if MODEL_PATH.exists():
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print("Failed to load site model:", e)
    return None

def _vectorize(features: dict):
    vals = []
    for k in FEATURE_ORDER:
        v = features.get(k, None)
        if v is None:
            # safe defaults
            v = {
                "humidity": 65,
                "temperature": 26,
                "wind_speed": 2,
                "ndvi": 0.15,
                "lst_night_c": 27,
                "dist_coast_km": 10,
                "pm25_mean": 45,
            }[k]
        vals.append(float(v))
    return np.array(vals, dtype=float).reshape(1, -1)

def predict_site_liters(model, features: dict) -> float:
    """
    Returns expected liters/day for the site given the feature dict.
    If model is None, returns a heuristic approximation.
    """
    if model is None:
        # simple heuristic fallback
        hum = features.get("humidity", 65)
        temp = features.get("temperature", 26)
        wind = features.get("wind_speed", 2)
        ndvi = features.get("ndvi", 0.15)
        lstn = features.get("lst_night_c", 27)
        coast = features.get("dist_coast_km", 10)
        pm25 = features.get("pm25_mean", 45)
        fog_prob = max(0.0, min(1.0, (hum - 55) / 40 * (1.1 - (temp - 18)/25)))
        liters = (10.0 * fog_prob) * (1.0 + 0.4*ndvi) * (1.0 - 0.03*wind) * (1.0 - 0.01*pm25/100) * (1.0 + 0.15*(30 - min(lstn, 30))/10) * (1.0 + 0.1*(20 - min(coast, 20))/20)
        return max(0.0, float(liters))
    x = _vectorize(features)
    y = model.predict(x)[0]
    return max(0.0, float(y))
