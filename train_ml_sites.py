
# train_site_model.py
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CSV = DATA_DIR / "site_features.csv"   # optional organizer file
OUT = DATA_DIR / "site_model.joblib"

FEATURES = ["humidity","temperature","wind_speed","ndvi","lst_night_c","dist_coast_km","pm25_mean"]

def synthesize(n=3000):
    rng = np.random.default_rng(42)
    humidity     = rng.uniform(45, 95, n)
    temperature  = rng.uniform(18, 36, n)
    wind_speed   = rng.uniform(0.3, 6.0, n)
    ndvi         = rng.uniform(0.0, 0.45, n)
    lst_night_c  = rng.uniform(22, 34, n)
    dist_coast_km= rng.uniform(0, 40, n)
    pm25_mean    = rng.uniform(10, 120, n)

    # latent fog probability (cooler nights + higher humidity + lower wind)
    fog_prob = np.clip((humidity-55)/40, 0, 1) * np.clip(1.2 - (temperature-18)/22, 0.2, 1.2) * np.clip(1.1 - wind_speed/8, 0.5, 1.1)
    # expected liters/day ~ area*efficiency*fog_prob * modifiers (ndvi↑, pm25↓, lst_night↓, coast closer↑)
    liters = 10.0 * fog_prob * (1 + 0.5*ndvi) * (1 - 0.002*pm25_mean) * (1 + 0.2*(30 - lst_night_c)/10) * (1 + 0.15*(20 - np.clip(dist_coast_km,0,20))/20)
    noise = rng.normal(0, 0.8, n)
    liters = np.clip(liters + noise, 0, None)

    df = pd.DataFrame({
        "humidity": humidity,
        "temperature": temperature,
        "wind_speed": wind_speed,
        "ndvi": ndvi,
        "lst_night_c": lst_night_c,
        "dist_coast_km": dist_coast_km,
        "pm25_mean": pm25_mean,
        "liters": liters
    })
    return df

def load_or_build():
    if CSV.exists():
        df = pd.read_csv(CSV)
        # if no liters column, approximate with heuristic so model can learn structure
        if "liters" not in df.columns:
            h = df.get("humidity", pd.Series(65, index=df.index))
            t = df.get("temperature", pd.Series(26, index=df.index))
            w = df.get("wind_speed", pd.Series(2, index=df.index))
            nd= df.get("ndvi", pd.Series(0.15, index=df.index))
            ls= df.get("lst_night_c", pd.Series(27, index=df.index))
            dc= df.get("dist_coast_km", pd.Series(10, index=df.index))
            pm= df.get("pm25_mean", pd.Series(45, index=df.index))
            fog_prob = np.clip((h-55)/40, 0, 1) * np.clip(1.2 - (t-18)/22, 0.2, 1.2) * np.clip(1.1 - w/8, 0.5, 1.1)
            liters = 10.0 * fog_prob * (1 + 0.5*nd) * (1 - 0.002*pm) * (1 + 0.2*(30 - ls)/10) * (1 + 0.15*(20 - np.clip(dc,0,20))/20)
            df["liters"] = liters
        df = df[[*FEATURES, "liters"]].dropna()
        if len(df) < 200:
            df = pd.concat([df, synthesize(2500-len(df))], ignore_index=True)
    else:
        df = synthesize(3000)
    return df

if __name__ == "__main__":
    df = load_or_build()
    X = df[FEATURES].values
    y = df["liters"].values
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=120, random_state=42)
    model.fit(Xtr, ytr)
    print("Train R²:", model.score(Xtr, ytr), " Test R²:", model.score(Xte, yte))
    joblib.dump(model, OUT)
    print("Saved model to:", OUT)