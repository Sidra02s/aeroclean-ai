# main.py
from flask import Flask, jsonify, request
import numpy as np
from sqlmodel import select
from models import Metric, Net, Alert
from db import get_session
from datetime import datetime, timedelta
import requests, os
from ml_sites import load_site_model, predict_site_liters

from ml import load_model, fog_prob, estimate_capture
from flask_cors import CORS


app = Flask(__name__)
CORS(app)
model = load_model()
site_model = load_site_model()

# --- API KEYS ---
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_KEY")
OPENAQ_BASE = "https://api.openaq.org/v2/measurements"

# --- External fetchers ---
def fetch_weather(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = requests.get(url, timeout=5).json()
        return {
            "temperature": res["main"]["temp"],
            "humidity": res["main"]["humidity"],
            "wind_speed": res["wind"]["speed"],
            "visibility": res.get("visibility", 10000)
        }
    except:
        return {"temperature": 25, "humidity": 70, "wind_speed": 2, "visibility": 10000}

def fetch_aqi(city="Dubai"):
    try:
        url = f"{OPENAQ_BASE}?city={city}&parameter=pm25&limit=1&sort=desc"
        res = requests.get(url, timeout=5).json()
        if res.get("results"):
            pm25 = res["results"][0]["value"]
            aqi = min(500, int(pm25 * 4))
            return {"pm25": pm25, "aqi": aqi}
    except:
        pass
    return {"pm25": None, "aqi": None}


# ---------------- Per-Net Calendar ----------------
def dashboard_data_with_params(net_id, start, end, calendar_only=False):
    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    with get_session() as session:
        stmt = select(Metric).where(
            Metric.net_id == net_id,
            Metric.date >= start_date,
            Metric.date <= end_date
        )
        metrics = session.exec(stmt).all()
        net = session.exec(select(Net).where(Net.id == net_id)).first()
        if net:
            area_m2, mesh_type, lat, lon = net.area_m2, net.mesh_type, net.lat, net.lon
        else:
            area_m2, mesh_type, lat, lon = 10, "standard", 25.276987, 55.296249

    calendar = []
    dates, aqi_values = [], []
    humidity_values, water_values = [], []

    for m in metrics:
        # Live weather & AQI if today
        if m.date == datetime.today().date():
            weather = fetch_weather(lat, lon)
            aqi_info = fetch_aqi("Dubai")
            humidity = weather["humidity"]
            temperature = weather["temperature"]
            wind_speed = weather["wind_speed"]
            visibility = weather["visibility"]
            pm25 = aqi_info["pm25"]
            aqi_val = aqi_info["aqi"]
        else:
            humidity = m.humidity
            temperature = getattr(m, "temperature", 25)
            wind_speed = getattr(m, "wind_speed", 0)
            visibility = getattr(m, "visibility", None)
            pm25 = m.pm25
            aqi_val = m.aqi

        fog_probability = fog_prob(humidity, temperature, datetime.now().hour, model)
        water_l = estimate_capture(area_m2, fog_probability, mesh_type)

        day_data = {
            "date": m.date.isoformat(),
            "humidity": humidity,
            "water_l": water_l,
            "fog_prob": fog_probability,
            "temperature": temperature,
            "wind_speed": wind_speed,
            "visibility": visibility,
            "pm25": pm25,
            "aqi": aqi_val
        }
        calendar.append(day_data)

        dates.append(m.date.isoformat())
        aqi_values.append(aqi_val)
        humidity_values.append(humidity)
        water_values.append(water_l)

    if calendar_only:
        return calendar
    
    total_water = sum(day["water_l"] for day in calendar)

    return {
        "calendar": calendar,
        "total_water": total_water,
        "charts": {
            "aqi": {"dates": dates, "values": aqi_values},
            "water_vs_humidity": {"humidity": humidity_values, "water_l": water_values}
        }
    }


# ---------------- Aggregated Charts ----------------
def aggregate_charts_for_all_nets(start_date, end_date):
    with get_session() as session:
        metrics = session.exec(
            select(Metric).where(Metric.date >= start_date, Metric.date <= end_date)
        ).all()

    all_dates = sorted(list({m.date for m in metrics}))
    water_vs_humidity = {"humidity": [], "water_l": []}
    aqi_chart = {"dates": [], "values": []}

    for d in all_dates:
        day_metrics = [m for m in metrics if m.date == d]
        avg_humidity = np.mean([m.humidity for m in day_metrics])
        total_water = np.sum([m.water_l for m in day_metrics])
        avg_aqi = np.mean([m.aqi for m in day_metrics if m.aqi is not None])

        water_vs_humidity["humidity"].append(avg_humidity)
        water_vs_humidity["water_l"].append(total_water)

        aqi_chart["dates"].append(d.isoformat())
        aqi_chart["values"].append(avg_aqi if avg_aqi else 0)

    return {
        "aqi": aqi_chart,
        "water_vs_humidity": water_vs_humidity
    }


# ---------------- Optimized Locations ----------------
COAST_LAT, COAST_LON = 25.2, 55.3  

# Haversine function
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

# Optimized locations generator
def get_optimized_locations(top_n=5):
    min_lat, max_lat, min_lon, max_lon = 24.0, 26.0, 54.0, 56.0
    num_candidates = 100
    candidates = [
        {"lat": np.random.uniform(min_lat, max_lat),
        "lon": np.random.uniform(min_lon, max_lon)}
        for _ in range(num_candidates)
    ]

    results = []
    for loc in candidates:
        dist_coast = haversine_km(loc["lat"], loc["lon"], COAST_LAT, COAST_LON)
        features = {
            "humidity": 60 + np.random.uniform(-5,5),
            "temperature": 26 + np.random.uniform(-2,2),
            "wind_speed": 2 + np.random.uniform(-0.5,0.5),
            "ndvi": 0.1 + np.random.uniform(0,0.1),
            "lst_night_c": 27 + np.random.uniform(-2,2),
            "dist_coast_km": dist_coast,
            "pm25_mean": 40 + np.random.uniform(-5,10)
        }
        predicted_liters = predict_site_liters(site_model, features)
        results.append({
            "lat": loc["lat"],
            "lon": loc["lon"],
            "score": round(predicted_liters,2),
            "predicted_water_l": round(predicted_liters,2),
            "avg_humidity": round(features["humidity"],2),
            "fog_probability": None,
            "recommended_mesh": "hydrophilic"
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]

# API route
@app.route("/optimized_locations", methods=["GET"])
def optimized_locations_endpoint():
    top_n = int(request.args.get("top_n", 5))
    locations = get_optimized_locations(top_n=top_n)
    return jsonify({"optimized_locations": locations})




# ---------------- Alerts ----------------
def get_all_alerts():
    with get_session() as session:
        alerts = session.exec(select(Alert)).all()
        return [{"net_id": a.net_id, "type": a.type, "message": a.message, "ts": a.ts.isoformat()} for a in alerts]


# ---------------- Root Route ----------------
@app.route("/", methods=["GET"])
def root_dashboard():
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=90)
    default_net = "net-1"

    calendar_json = dashboard_data_with_params(default_net, start_date.isoformat(), end_date.isoformat(), calendar_only=True)
    charts_json = aggregate_charts_for_all_nets(start_date, end_date)
    optimized_json = get_optimized_locations(start_date, end_date, top_n=5)
    alerts_json = get_all_alerts()
    total_water = sum(day["water_l"] for day in calendar_json)

    return jsonify({
        "calendar": calendar_json,
        "charts": charts_json,
        "optimized_locations": optimized_json,
        "alerts": alerts_json,
        "total_water": total_water
    })


# ---------------- Single Day Calendar Endpoint ----------------
@app.route("/api/calendar/<date_str>", methods=["GET"])
def get_calendar_day(date_str):
    """
    Fetch calendar data for a single day
    """
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    default_net = "net-1"
    day_data = dashboard_data_with_params(
        default_net,
        start=selected_date.isoformat(),
        end=selected_date.isoformat(),
        calendar_only=True
    )

    if not day_data:
        return jsonify({"error": "No data for this day"}), 404

    return jsonify(day_data[0])


if __name__ == "__main__":
    app.run(debug=True)
