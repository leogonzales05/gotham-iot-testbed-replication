import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

project = "c09e7ed4-88b1-401f-a934-deaca6d79683"
base = "http://127.0.0.1:3080/v2/projects/" + project

def api(path="", method="GET"):
    with urlopen(Request(base + path, method=method), timeout=90) as r:
        body = r.read()
        return json.loads(body) if body else None

targets = [
    "iotsim-mirai-cnc-1",
    "iotsim-mirai-scan-listener-1",
    "iotsim-mirai-wget-loader-1",
    "iotsim-mirai-loader-1",
    "iotsim-mirai-bot-1",
]

info = api()
if info["status"] != "opened" or info["auto_close"]:
    raise SystemExit("Se necesita el proyecto abierto con auto_close=False.")

nodes = api("/nodes")
if any(n["node_type"] in ("cloud", "nat") for n in nodes):
    raise SystemExit("Se encontró una conexión Cloud/NAT. Revisar topología.")

by_name = {n["name"]: n for n in nodes}
for name in targets:
    if name not in by_name:
        raise SystemExit("Falta el nodo: " + name)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = Path("replication/results") / ("mirai-" + stamp)
output.mkdir(parents=True)
Path.home().joinpath("gotham-current-mirai-dir.txt").write_text(
    str(output.resolve()) + "\n"
)
(output / "nodes-before.json").write_text(json.dumps(nodes, indent=2))

for name in targets:
    node = by_name[name]
    if node["status"] != "started":
        api("/nodes/" + node["node_id"] + "/start", "POST")
    print("Iniciado:", name, flush=True)

print("Esperando 30 segundos al arranque de los servicios...", flush=True)
time.sleep(30)

summary = []
for name in targets:
    container = "GNS3." + name + "." + project
    c = json.loads(subprocess.check_output(
        ["docker", "inspect", container], text=True
    ))[0]

    entry = {
        "name": name,
        "state": c["State"]["Status"],
        "network_disabled": c["Config"].get("NetworkDisabled"),
        "network_mode": c["HostConfig"].get("NetworkMode"),
        "docker_networks": c["NetworkSettings"].get("Networks"),
    }
    summary.append(entry)
    print(json.dumps(entry), flush=True)

    log = subprocess.run(
        ["docker", "logs", "--tail", "40", container],
        capture_output=True, text=True
    )
    (output / (name + ".startup.log")).write_text(log.stdout + log.stderr)
    print(log.stdout + log.stderr, flush=True)

(output / "startup.json").write_text(json.dumps(summary, indent=2))
print("Evidencias:", output.resolve())
print("El programa del bot no se ha ejecutado desde este script.")
