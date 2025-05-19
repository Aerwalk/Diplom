from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import meshtastic.serial_interface
import threading, time, json, os, random
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ROUTE_DIR = "routes"
TRACK_DIR = "tracks"
os.makedirs(ROUTE_DIR, exist_ok=True)
os.makedirs(TRACK_DIR, exist_ok=True)

interface = meshtastic.serial_interface.SerialInterface()
nodes_data = {}

def append_to_track(node_id, lat, lng):
    path = os.path.join(TRACK_DIR, f"{node_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
    data.append({
        "lat": lat,
        "lng": lng,
        "time": datetime.utcnow().isoformat()
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_nodes():
    while True:
        for node_id, node in interface.nodes.items():
            pos = node.get('position', {})
            user = node.get('user', {})
            metrics = node.get('deviceMetrics', {})

            battery = metrics.get("batteryLevel")
            voltage = metrics.get("voltage")

            if pos:
                nodes_data[node_id] = {
                    "id": node_id,
                    "name": user.get('longName', node_id),
                    "lat": pos.get('latitude'),
                    "lng": pos.get('longitude'),
                    "alt": pos.get('altitude', 0),
                    "battery": round(battery ) if battery is not None else None,
                    "voltage": round(voltage, 2) if voltage is not None else None
                }
                append_to_track(node_id, pos.get('latitude'), pos.get('longitude'))

        time.sleep(10)


@app.get("/api/locations")
def get_locations():
    return list(nodes_data.values())

@app.get("/api/simulate_extend")
def simulate_extend(id: str = Query(...)):
    original_path = os.path.join(TRACK_DIR, f"{id}.json")
    new_path = os.path.join(TRACK_DIR, f"Emu_{id}.json")

    if os.path.exists(original_path):
        with open(original_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    # Генерация 5 дополнительных точек
    for _ in range(5):
        last = data[-1] if data else {"lat": 51.5, "lng": -0.1}
        new_point = {
            "lat": round(last["lat"] + random.uniform(-0.0003, 0.0003), 6),
            "lng": round(last["lng"] + random.uniform(-0.0003, 0.0003), 6),
            "time": datetime.utcnow().isoformat()
        }
        data.append(new_point)

    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "file": f"Emu_{id}.json", "points": len(data)}

@app.get("/api/export_route")
def export_route(id: str = Query(...)):
    path = os.path.join(ROUTE_DIR, f"{id}_route.json")
    return FileResponse(path, media_type="application/json", filename=f"{id}_route.json")
#uvicorn main:app --reload --host 0.0.0.0 --port 8000
threading.Thread(target=update_nodes, daemon=True).start()
