import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

project_id = "c09e7ed4-88b1-401f-a934-deaca6d79683"
base = "http://127.0.0.1:3080/v2/projects/" + project_id

def api(path="", method="GET", data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(
        base + path, data=body, method=method,
        headers={"Content-Type": "application/json"}
    )
    with urlopen(request, timeout=60) as response:
        content = response.read()
        return json.loads(content) if content else None

project = api()
if project["status"] != "opened" or project["auto_close"]:
    raise SystemExit("El proyecto debe estar abierto y auto_close=False.")

output = Path(
    Path.home().joinpath("gotham-current-mirai-dir.txt").read_text().strip()
)
if not output.is_dir():
    raise SystemExit("No existe la carpeta de evidencias de preparación.")

manifest = output / "captures.json"
if manifest.exists():
    raise SystemExit("Ya existe captures.json. No se iniciaron más capturas.")

nodes = {n["name"]: n for n in api("/nodes")}
links = api("/links")
targets = (
    "iotsim-mirai-bot-1",
    "iotsim-mirai-cnc-1",
    "iotsim-mirai-scan-listener-1",
)

selected = []
for name in targets:
    node = nodes[name]
    if node["status"] != "started":
        raise SystemExit("El nodo no está iniciado: " + name)
    matches = [
        link for link in links
        if any(
            end["node_id"] == node["node_id"]
            and end["adapter_number"] == 0
            and end["port_number"] == 0
            for end in link["nodes"]
        )
    ]
    if len(matches) != 1:
        raise SystemExit("No se encontró un enlace eth0 único: " + name)
    if matches[0].get("capturing"):
        raise SystemExit("Ya existe una captura activa en: " + name)
    selected.append((name, matches[0]))

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
records = []
manifest.write_text("[]\n")

for name, link in selected:
    filename = f"{name}-{stamp}.pcap"
    api("/links/" + link["link_id"] + "/start_capture", "POST",
        {"capture_file_name": filename})
    record = {
        "node": name,
        "link_id": link["link_id"],
        "filename": filename,
        "requested_start_utc": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    manifest.write_text(json.dumps(records, indent=2) + "\n")
    state = api("/links/" + link["link_id"])
    print(name, "| Capturando:", state.get("capturing"), flush=True)
    if not state.get("capturing"):
        raise SystemExit("No se confirmó la captura. Revisar antes de continuar.")

print("Registro:", manifest)
print("Capturas iniciadas. Este script no ejecuta el bot.")
print("No tienen parada automática todavía.")
