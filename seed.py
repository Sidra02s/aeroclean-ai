# seed_calendar.py
import datetime
from sqlmodel import select
from db import init_db, get_session
from models import Net, Metric, Alert
import requests
from meteostat import Point, Daily
from time import sleep
from random import random

# ---------------- CONFIG -----------------
OPENAQ_RADIUS = 10000  # meters
DAYS_BACK = 90

# ---------------- INIT DB -----------------
init_db()
db = get_session()

# Ensure nets exist
existing_nets = db.exec(select(Net)).all()
if not existing_nets:
    nets = [
        Net(id="net-1", lat=25.276987, lon=55.296249, area_m2=20, mesh_type="hydrophilic"),
        Net(id="net-2", lat=24.453884, lon=54.377344, area_m2=15, mesh_type="standard"),
        Net(id="net-3", lat=25.405216, lon=55.513643, area_m2=12, mesh_type="standard"),
    ]
    for net in nets:
        db.add(net)
    db.commit()
    existing_nets = nets

# ---------------- HELPERS -----------------
def get_aqi_openaq(lat, lon, start, end):
    """Fetch AQI (pm25/pm10) from OpenAQ in a date range and aggregate daily averages."""
    daily_data = {}
    page = 1
    while True:
        url = "https://api.openaq.org/v2/measurements"
        params = {
            "coordinates": f"{lat},{lon}",
            "radius": OPENAQ_RADIUS,
            "parameter[]": ["pm25", "pm10"],
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "limit": 100,
            "page": page
        }
        res = requests.get(url, params=params).json()
        results = res.get("results", [])
        if not results:
            break
        for r in results:
            dt = r["date"]["utc"][:10]
            param = r["parameter"]
            value = r["value"]
            if dt not in daily_data:
                daily_data[dt] = {"pm25": None, "pm10": None}
            daily_data[dt][param] = value
        if page >= res.get("meta", {}).get("totalPages", 1):
            break
        page += 1
        sleep(0.2)
    for dt in daily_data:
        pm25 = daily_data[dt].get("pm25", 0)
        daily_data[dt]["aqi"] = min(500, int(pm25 * 4))
    return daily_data

def get_historical_weather(lat, lon, start, end):
    """Fetch daily historical weather data using Meteostat."""
    location = Point(lat, lon)
    data = Daily(location, start, end).fetch()
    weather_by_day = {}
    for date, row in data.iterrows():
        weather_by_day[date.date().isoformat()] = {
            "humidity": row.get("rhum", 60) or 60,
            "temperature": row.get("tavg", 30) or 30,
            "precipitation": row.get("prcp", 0) or 0
        }
    return weather_by_day

# ---------------- SEED METRICS -----------------
today = datetime.date.today()
start_date = today - datetime.timedelta(days=DAYS_BACK)

for net in existing_nets:
    # Fetch AQI and weather
    aqi_data = get_aqi_openaq(net.lat, net.lon, start_date, today)
    weather_data = get_historical_weather(net.lat, net.lon, start_date, today)

    for i in range(DAYS_BACK + 1):
        d = start_date + datetime.timedelta(days=i)
        date_str = d.isoformat()

        # AQI values
        aq = aqi_data.get(date_str, {})
        aqi = aq.get("aqi", 50)
        pm25 = aq.get("pm25", 10)
        pm10 = aq.get("pm10", 15)

        # Weather values
        weather = weather_data.get(date_str, {})
        humidity = weather.get("humidity", 60)

        # Fog and water calculations
        fog_prob = 0.1
        if humidity > 90:
            fog_prob = 0.8
        elif humidity > 75:
            fog_prob = 0.5
        water = round(
            net.area_m2 * (0.12 if net.mesh_type == "hydrophilic" else 0.05) * fog_prob,
            2
        )

        metric = Metric(
            net_id=net.id,
            date=d,
            water_l=water,
            humidity=humidity,
            fog_prob=fog_prob,
            pm25=pm25,
            pm10=pm10,
            aqi=aqi
        )
        db.add(metric)

    # Optional demo alerts
    if random() < 0.3:
        alert = Alert(net_id=net.id, type="Low AQI", message="Demo alert: PM spike")
        db.add(alert)

db.commit()
db.close()
print(f"Seeded {DAYS_BACK} days of historical metrics for calendar display.")
