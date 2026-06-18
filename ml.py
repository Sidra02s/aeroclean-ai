# ml.py
import joblib
from pathlib import Path
import numpy as np
from typing import Optional

MODEL_PATH = Path("data/fog_model.joblib")

# mesh efficiency per m2 per probability unit (heuristic defaults)
MESH_EFF = {"standard": 0.05, "hydrophilic": 0.12}

def load_model():
    if MODEL_PATH.exists():
        try:
            model = joblib.load(MODEL_PATH)
            return model
        except Exception as e:
            print("Failed loading model:", e)
    return None

# ---------------- Fog Probability ----------------
def fog_prob(humidity: float, temperature: float, hour: int = 0, model=None) -> float:
    if model:
        try:
            import pandas as pd
            features = pd.DataFrame([{
                "humidity": humidity,
                "temp": temperature,
                "hour": hour
            }])
            pred = model.predict(features)[0]
            # pred = model.predict(np.array(features).reshape(1, -1))[0]
            return float(max(0.0, min(1.0, pred)))
        except Exception as e:
            print("ML prediction failed, using heuristic:", e)
    # fallback heuristic
    base = max(0.0, (humidity - 60) / 40.0)
    temp_factor = 1.0 if temperature <= 25 else 0.6
    night_factor = 1.2 if 0 <= hour <= 6 else 0.9
    prob = base * temp_factor * night_factor
    return min(1.0, prob)


# ---------------- Water Capture ----------------
def estimate_capture(area_m2: float, fog_probability: float, mesh_type: str = "standard") -> float:
    """
    Estimate liters of water collected given net area, fog probability, mesh type.
    """
    eff = MESH_EFF.get(mesh_type, MESH_EFF["standard"])
    liters = area_m2 * eff * fog_probability
    return float(liters)
