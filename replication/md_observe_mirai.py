import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

repo = Path(__file__).resolve().parent.parent
output = Path(
    Path.home().joinpath("gotham-current-mirai-dir.txt").read_text().strip()
)
base = (
    "http://127.0.0.1:3080/v2/projects/"
    "c09e7ed4-88b1-401f-a934-deaca6d79683"
)
captures = json.loads((output / "captures.json").read_text())
record_file = output / "observation.json"

if record_file.exists():
    raise SystemExit("Ya existe una observación. No se ejecutó nuevamente.")

def api(path="", method="GET"):
    with urlopen(Request(base + path, method=method), timeout=60) as response:
        content = response.read()
        return json.loads(content) if content else None

def utc():
    return datetime.now(timezone.utc).isoformat()

nodes = {n["name"]: n for n in api("/nodes")}
bot = nodes["iotsim-mirai-bot-1"]

for capture in captures:
    if not api("/links/" + capture["link_id"]).get("capturing"):
        raise SystemExit("Falta una captura activa: " + capture["node"])

record = {
    "start_utc": utc(),
    "planned_observation_seconds": 300,
    "behavior_validated": False,
    "note": "La salida del lanzador no confirma éxito del experimento.",
}
record_file.write_text(json.dumps(record, indent=2))

try:
    print("Ejecutando el lanzador original...", flush=True)
    with (output / "run_mirai.py.log").open("w") as log:
        result = subprocess.run(
            [str(repo / ".venv/bin/python"), "-u", "run_mirai.py"],
            cwd=repo / "src",
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    record["launcher_exit_code"] = result.returncode
    print((output / "run_mirai.py.log").read_text(), flush=True)
    if result.returncode:
        raise RuntimeError("El lanzador terminó con error.")

    for minute in range(5):
        time.sleep(60)
        print(f"Observación: {minute + 1}/5 minutos", flush=True)

except Exception as error:
    record["error"] = repr(error)
    print("Error:", error, flush=True)

finally:
    print("Deteniendo el nodo del bot inicial...", flush=True)
    try:
        api("/nodes/" + bot["node_id"] + "/stop", "POST")
        record["bot_stop_confirmed"] = True
    except Exception as error:
        record["bot_stop_error"] = repr(error)

    record["capture_stops"] = []
    for capture in captures:
        entry = {"node": capture["node"]}
        try:
            api("/links/" + capture["link_id"] + "/stop_capture", "POST")
            entry["stopped"] = True
        except Exception as error:
            entry["error"] = repr(error)
        record["capture_stops"].append(entry)

    for name in (
        "iotsim-mirai-cnc-1",
        "iotsim-mirai-scan-listener-1",
        "iotsim-mirai-wget-loader-1",
        "iotsim-mirai-loader-1",
        "iotsim-mirai-bot-1",
    ):
        container = (
            "GNS3." + name +
            ".c09e7ed4-88b1-401f-a934-deaca6d79683"
        )
        result = subprocess.run(
            ["docker", "logs", "--tail", "200", container],
            capture_output=True, text=True
        )
        text = result.stdout + result.stderr
        (output / (name + ".observation.log")).write_text(text)
        if "scan-listener" in name:
            print("\n=== REPORTES DEL SCAN LISTENER ===")
            print(text)

    record["end_utc"] = utc()
    record_file.write_text(json.dumps(record, indent=2))
    print("\nEvidencias:", output)
    print("Falta analizar PCAP y registros para validar el comportamiento.")
    print("Los otros servicios del laboratorio permanecen iniciados.")
