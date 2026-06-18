# train_ml.py
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
from pathlib import Path

N = 2000
humidity = np.random.uniform(30, 100, N)
temp = np.random.uniform(15, 40, N)
hour = np.random.randint(0,24,N)
# synthetic fog target
fog = np.clip((humidity-50)/50 * (1.2 - (temp-20)/30) * (1 + (hour<6)*0.3), 0, 1)
fog += np.random.normal(0, 0.05, N)
fog = np.clip(fog, 0, 1)
df = pd.DataFrame({"humidity": humidity, "temp": temp, "hour": hour, "fog": fog})
X = df[["humidity","temp","hour"]]
y = df["fog"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestRegressor(n_estimators=50)
model.fit(X_train, y_train)
print("train score:", model.score(X_train, y_train), "test score:", model.score(X_test, y_test))
Path("data").mkdir(exist_ok=True)
joblib.dump(model, "data/fog_model.joblib")
print("saved model to data/fog_model.joblib")
