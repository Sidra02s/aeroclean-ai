# openweather.py
import os
import asyncio
from datetime import datetime, date
from typing import Tuple, Optional
import httpx
from dotenv import load_dotenv

from db import get_session
from models import Metric, Net

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    raise RuntimeError("Set OPENWEATHER_API_KEY in .env")

WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
AIR_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

# Helper: get current weather (temp, humidity, wind)
async def fetch_weather(lat: float, lon: float) -> Optional[dict]:
    params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(WEATHER_URL, params=params)
        r.raise_for_status()
        return r.json()

# Helper: get air pollution (pm2_5, pm10, aqi)
async def fetch_air(lat: float, lon: float) -> Optional[dict]:
    params = {"lat": lat, "lon": lon, "appid": API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(AIR_URL, params=params)
        r.raise_for_status()
        return r.json()

def pm25_to_aqi(pm25):
    """
    Convert pm2.5 (µg/m3) to US EPA AQI (0-500) using breakpoints.
    Returns int AQI.
    """
    if pm25 is None:
        return None

    # breakpoints based on EPA table (µg/m3)
    breakpoints = [
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500),
    ]
    for (c_low, c_high, a_low, a_high) in breakpoints:
        if pm25 >= c_low and pm25 <= c_high:
            # linear interpolation
            aqi = ((a_high - a_low) / (c_high - c_low)) * (pm25 - c_low) + a_low
            return int(round(aqi))
    # if beyond table
    return 500

# Convert OpenWeather payloads to our fields
def parse_openweather(weather_json: dict, air_json: dict):
    temp = None
    humidity = None
    pm25 = None
    pm10 = None
    aqi_us = None

    if weather_json:
        main = weather_json.get("main", {})
        temp = main.get("temp")
        humidity = main.get("humidity")

    if air_json:
        lst = air_json.get("list", [])
        if lst:
            air0 = lst[0]
            comps = air0.get("components", {})
            pm25 = comps.get("pm2_5")
            pm10 = comps.get("pm10")
            try:
                aqi_us = pm25_to_aqi(pm25) if pm25 is not None else None
            except Exception:
                aqi_us = None

    # Log for debugging
    print(f"[openweather.parse] temp={temp}, humidity={humidity}, pm25={pm25}, pm10={pm10}, aqi_us={aqi_us}")
    return temp, humidity, pm25, pm10, aqi_us


# Write snapshot into Metric table (one row per date per net)
def store_snapshot(net_id: str, temp: float, humidity: float, pm25: float, pm10: float, aqi_us: int):
    with get_session() as s:
        today = date.today()
        # attempt to find existing row for today
        existing = s.query(Metric).filter(Metric.net_id == net_id, Metric.date == today).first()
        if existing:
            # update latest reading (you may choose to sum water_l from sensor or estimate)
            existing.humidity = humidity
            existing.pm25 = pm25 or existing.pm25
            existing.pm10 = pm10 or existing.pm10
            existing.aqi = aqi_us
            
            existing.last_update = datetime.utcnow()
            s.add(existing)
        else:
            m = Metric(
                net_id = net_id,
                date = today,
                water_l = 0.0,      # leave 0 or estimate using ML
                humidity = humidity or 0.0,
                fog_prob = 0.0,
                pm25 = pm25 or 0.0,
                pm10 = pm10 or 0.0,
                aqi = aqi_us or 0.0,
            )
            s.add(m)
        s.commit()

# Main routine: fetch & store for a given net
async def fetch_and_store_for_net(net):
    try:
        w = await fetch_weather(net.lat, net.lon)
        a = await fetch_air(net.lat, net.lon)
        # debug: print raw responses (only during dev)
        print(f"[openweather.raw] net={net.id} weather_keys={list(w.keys()) if w else None}")
        print(f"[openweather.raw] net={net.id} air_keys={list(a.keys()) if a else None}")
        temp, humidity, pm25, pm10, aqi_us = parse_openweather(w, a)
        store_snapshot(net.id, temp, humidity, pm25, pm10, aqi_us)
    except Exception as e:
        print(f"OpenWeather fetch error for net {net.id}: {e}")


# Scheduler: fetch for all nets periodically
async def periodic_openweather_poll(interval_seconds: int = 900):
    # interval_seconds default 900 = 15 minutes
    while True:
        with get_session() as s:
            nets = s.query(Net).all()
            # stagger: fire tasks for each net
            tasks = [fetch_and_store_for_net(net) for net in nets]
        # run concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(interval_seconds)

