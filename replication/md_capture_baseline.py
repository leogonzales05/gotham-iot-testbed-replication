"""Supervised normal-traffic capture, reconstructed from the successful session."""
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "http://127.0.0.1:3080/v2"
ROOT = Path(__file__).resolve().parent


def api(method, path, data=None):
    response = requests.request(method, BASE + path, json=data, timeout=90)
    if not response.ok:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json() if response.content else None


def main():
    projects = api("GET", "/projects")
    project = next(p for p in projects if p["name"] == "gotham_scenario")
    project_path = "/projects/" + project["project_id"]
    if project["status"] != "opened" or project["auto_close"]:
        raise RuntimeError("El proyecto debe estar abierto con auto_close=False.")
    nodes = api("GET", project_path + "/nodes")
    router = next(n for n in nodes if n["name"] == "VyOS1.3.0-1")
    links = [link for link in api("GET", project_path + "/links") if any(
        end["node_id"] == router["node_id"] and end["adapter_number"] == 0
        and end["port_number"] == 0 for end in link["nodes"])]
    if len(links) != 1:
        raise RuntimeError("No se identificó un único enlace en RNORTH eth0.")
    link = links[0]
    endpoints = {end["node_id"] for end in link["nodes"]}
    if any(n["status"] != "started" for n in nodes if n["node_id"] in endpoints):
        raise RuntimeError("Los extremos de la captura deben estar encendidos.")
    if link["capturing"]:
        raise RuntimeError("Ya existe una captura activa. Se conserva.")
    if shutil.disk_usage(Path.home()).free < 5 * 1024**3:
        raise RuntimeError("Quedan menos de 5 GiB libres.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "results" / stamp
    folder.mkdir(parents=True)
    (folder / "nodes-before.json").write_text(json.dumps(nodes, indent=2))
    record_path = folder / "capture.json"
    record = {"planned_seconds": 3600, "completed": False,
              "project_id": project["project_id"], "link_id": link["link_id"]}
    path = project_path + "/links/" + link["link_id"]
    started = time.monotonic()
    capture_requested = False
    failure = None
    try:
        capture_requested = True
        api("POST", path + "/start_capture", {
            "capture_file_name": f"gotham-normal-60min-{stamp}.pcap",
            "data_link_type": "DLT_EN10MB"})
        started = time.monotonic()
        record["start_utc"] = datetime.now(timezone.utc).isoformat()
        state = api("GET", path)
        if not state["capturing"]:
            raise RuntimeError("GNS3 no confirmó la captura.")
        pcap = Path(state["capture_file_path"])
        record["pcap"] = str(pcap)
        Path.home().joinpath("gotham-current-pcap.txt").write_text(str(pcap))
        record_path.write_text(json.dumps(record, indent=2))
        previous = pcap.stat().st_size
        for minute in range(1, 61):
            remaining = started + minute * 60 - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            if api("GET", project_path)["status"] != "opened":
                raise RuntimeError("El proyecto se cerró.")
            if not api("GET", path)["capturing"]:
                raise RuntimeError("La captura se interrumpió.")
            size = pcap.stat().st_size
            record.update(last_minute=minute, last_size_bytes=size)
            record_path.write_text(json.dumps(record, indent=2))
            print(f"Minuto {minute}/60: {size / 1024**2:.1f} MiB", flush=True)
            if size <= previous:
                raise RuntimeError("El PCAP no creció durante el último minuto.")
            previous = size
        record["completed"] = True
    except BaseException as exc:
        failure = exc
        record["error"] = str(exc)
    finally:
        if capture_requested:
            try:
                api("POST", path + "/stop_capture")
                record["stop_confirmed"] = True
            except Exception as exc:
                record.update(completed=False, stop_confirmed=False, stop_error=str(exc))
        record["end_utc"] = datetime.now(timezone.utc).isoformat()
        record["elapsed_seconds"] = time.monotonic() - started
        if record.get("pcap") and Path(record["pcap"]).exists():
            record["size_bytes"] = Path(record["pcap"]).stat().st_size
        record_path.write_text(json.dumps(record, indent=2))
        print("Registro:", record_path, flush=True)
    if failure or not record["completed"]:
        raise SystemExit("La corrida requiere revisión. Consulta capture.json.")
    print("Captura finalizada y parada confirmada.", flush=True)


if __name__ == "__main__":
    main()
