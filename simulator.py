# simulator.py
import requests, time, random, datetime

BASE = "http://127.0.0.1:8000"

def run_simulation(iterations=400, pause=0.2):
    net_ids = [
        {"id": "net-1", "area_m2": 30, "mesh": "standard"},
        {"id": "net-2", "area_m2": 50, "mesh": "hydrophilic"},
        {"id": "net-3", "area_m2": 40, "mesh": "standard"}
    ]

    for i in range(iterations):
        net = random.choice(net_ids)
        now = datetime.datetime.utcnow().isoformat()

        humidity = round(random.uniform(40, 95), 2)
        temperature = round(random.uniform(18, 36), 2)
        pm25 = round(random.uniform(10, 200), 2)

        payload = {
            "net_id": net["id"],
            "timestamp": now,
            "humidity": humidity,
            "temperature": temperature,
            "pm25": pm25,
            "area_m2": net["area_m2"],
            "mesh_type": net["mesh"]
        }

        try:
            r = requests.post(f"{BASE}/api/v1/sensor", json=payload, timeout=5)
            print(
                i, r.status_code, net["id"],
                "humidity:", humidity,
                "temp:", temperature,
                "pm25:", pm25
            )
        except Exception as e:
            print("err", e)

        time.sleep(pause)

if __name__ == "__main__":
    run_simulation()
