import argparse
import csv
import subprocess
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("pcap", type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()

if not args.pcap.is_file():
    raise SystemExit(f"No existe: {args.pcap}")

# Regla propia de clasificación, no confirmada como el método de los autores.
# ICMP tiene prioridad para no contar el paquete citado como tráfico separado.
priority = (
    "icmp", "icmpv6", "arp",
    "sdp", "rtsp",
    "coap", "mqtt", "dns", "ntp", "rtcp", "rtp",
    "dtls", "tls",
    "tcp", "udp", "ipv6", "ip", "eth",
)

args.output.parent.mkdir(parents=True, exist_ok=True)
errors = args.output.with_suffix(".errors.log")
counts = Counter()
unknown = Counter()

print("Analizando:", args.pcap, flush=True)

with errors.open("w") as log:
    process = subprocess.Popen(
        [
            "tshark", "-n", "-r", str(args.pcap),
            "--enable-heuristic", "rtp_udp",
            "-T", "fields", "-e", "frame.protocols",
        ],
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
    )
    for line in process.stdout:
        chain = line.strip()
        layers = set(chain.split(":"))
        category = next(
            (name for name in priority if name in layers), "other"
        )
        counts[category] += 1
        if category in ("udp", "ipv6", "ip", "eth", "other"):
            unknown[chain] += 1

    result = process.wait()

if result:
    raise SystemExit(f"TShark falló con código {result}. Revisa {errors}")

total = sum(counts.values())
if not total:
    raise SystemExit("No se encontraron paquetes.")

with args.output.open("w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["protocol", "packets", "percent"])
    for category, count in counts.most_common():
        writer.writerow([category, count, f"{100 * count / total:.9f}"])

method = args.output.with_suffix(".method.txt")
method.write_text(
    "Clasificación exclusiva propia: cada trama pertenece a una categoría.\n"
    "Fuente: frame.protocols de TShark con heurística rtp_udp habilitada.\n"
    "Se elige el primer protocolo presente según esta prioridad:\n"
    + " > ".join(priority)
    + "\nICMP/ICMPv6 conservan prioridad sobre protocolos de paquetes citados.\n"
    "El contenido data-text-lines de CoAP queda agrupado en CoAP.\n"
    "SDP queda separado de RTSP. TCP/UDP son categorías residuales.\n"
    "No se ha confirmado que esta sea la metodología de la Tabla V.\n"
    "La clasificación depende del reconocimiento de protocolos de TShark.\n"
)

unclassified = args.output.with_suffix(".unclassified.txt")
unclassified.write_text(
    "\n".join(
        f"{count}\t{chain}" for chain, count in unknown.most_common()
    ) + "\n"
)

print(f"\nTotal: {total}")
print(f"{'Protocolo':<12} {'Paquetes':>12} {'Porcentaje':>14}")
for category, count in counts.most_common():
    print(f"{category:<12} {count:>12} {100 * count / total:>13.6f}%")

print("\nTabla:", args.output)
print("Método:", method)
print("Cadenas sin identificar a nivel de aplicación:", unclassified)
print("Avisos:", errors)
