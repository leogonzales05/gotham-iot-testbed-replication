#!/usr/bin/env bash
set -euo pipefail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pcap=${1:-$(cat "$HOME/gotham-current-pcap.txt")}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$script_dir/results/analysis-$stamp"
mkdir -p "$out"
capinfos -M -c -s -a -e -u "$pcap" | tee "$out/summary.txt"
tshark --version > "$out/tshark-version.txt" 2> "$out/version-errors.log"
tshark -n -r "$pcap" --enable-heuristic rtp_udp -q -z io,phs \
    2> "$out/analysis-errors.log" | tee "$out/protocols.txt"
sha256sum "$pcap" | tee "$out/sha256.txt"
echo "Análisis guardado en $out"
