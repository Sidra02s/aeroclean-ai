# frontend.py
import streamlit as st
import requests
import datetime

BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="🌬️ AeroClean AI - Test Dashboard", layout="wide")

st.title("🌬️ AeroClean AI - Weather & AQI Test")

# --- Real-time AQI ---
st.header("Air Quality & Weather (Live)")

try:
    response = requests.get(f"{BASE}/api/v1/air/aqi?lat=25.2&lon=55.3")
    if response.status_code == 200:
        data = response.json()
        st.success("✅ API Connected")
        st.json(data)

        aqi = data["data"]["aqi"]
        pm25 = data["data"]["pm25"]
        pm10 = data["data"]["pm10"]

        col1, col2, col3 = st.columns(3)
        col1.metric("AQI", aqi)
        col2.metric("PM2.5", f"{pm25} µg/m³")
        col3.metric("PM10", f"{pm10} µg/m³")

    else:
        st.error(f"API error: {response.status_code}")
except Exception as e:
    st.error(f"Could not connect to backend: {e}")

# --- AQI History Simulation ---
st.header("AQI History (Last Few Minutes)")

# call backend multiple times to simulate history - graph
history = []
for i in range(100):  # 10 data points
    r = requests.get(f"{BASE}/api/v1/air/aqi?lat=25.2&lon=55.3").json()
    ts = datetime.datetime.now() - datetime.timedelta(minutes=(1000-i))
    history.append({"time": ts, "aqi": r["data"]["aqi"]})

import pandas as pd
df = pd.DataFrame(history)
st.line_chart(df.set_index("time")["aqi"])
