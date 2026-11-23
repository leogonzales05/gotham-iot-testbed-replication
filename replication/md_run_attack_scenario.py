#!/usr/bin/env python3
"""Orquestación de los lanzadores originales de Gotham y evidencias locales.

Ejecutar en la VM: .venv/bin/python replication/run_attack_scenario.py
No implementa ataques nuevos ni modifica los programas originales.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.home() / 'gotham-iot-testbed')
    parser.add_argument('--observe-seconds', type=int, default=300)
    parser.add_argument('--stages', nargs='+', choices=['mirai', 'merlin', 'mqtt'],
                        default=['mirai', 'merlin', 'mqtt'])
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not 60 <= args.observe_seconds <= 900:
        parser.error('--observe-seconds debe estar entre 60 y 900')
    repo = args.repo.resolve()
    python = repo / '.venv/bin/python'
    if not python.is_file():
        raise SystemExit('No existe el intérprete de la VM: ' + str(python))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = repo / 'replication/results' / ('attacks-' + stamp)
    output.mkdir(parents=True)
    base = 'http://127.0.0.1:3080/v2'

    def api(path, method='GET', data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(base + path, data=body, method=method,
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=120) as response:
                content = response.read()
                return json.loads(content) if content else None
        except HTTPError as error:
            raise RuntimeError(f'GNS3 {error.code}: {error.read().decode()}') from error

    def command(cmd, file, timeout=180):
        with file.open('w') as log:
            result = subprocess.run(cmd, cwd=repo / 'src', stdout=log,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        return result.returncode

    report = {'start_utc': utc(), 'stages': {}, 'scope':
              'Lanzadores originales Mirai, Merlin y Metasploit/MQTT. '
              'No automatiza Nmap, Masscan ni amplificación CoAP.',
              'remaining': ['Nmap/Masscan', 'amplificación CoAP'],
              'warning': 'Los cambios de contraseñas y Telnet de Mirai persisten. '
                         'La parada de nodos no restaura los dispositivos.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    projects = [p for p in api('/projects') if p['name'] == 'gotham_scenario']
    if len(projects) != 1 or projects[0]['status'] != 'opened':
        raise SystemExit('Se necesita un único proyecto gotham_scenario abierto.')
    project = projects[0]
    path = '/projects/' + project['project_id']
    if project['auto_close']:
        raise SystemExit('Configura auto_close=False antes de ejecutar.')
    nodes = {n['name']: n for n in api(path + '/nodes')}
    (output / 'nodes-before.json').write_text(json.dumps(list(nodes.values()), indent=2))
    if any(n['node_type'] in ('cloud', 'nat') for n in nodes.values()):
        raise SystemExit('Existe un conector Cloud/NAT; revisar aislamiento.')
    if any(n['status'] != 'started' for n in nodes.values()
           if n['node_type'] == 'qemu' or n['name'].startswith('OpenvSwitch')):
        raise SystemExit('Primero inicia la infraestructura con el lanzador base.')
    patch = repo / 'Dockerfiles/malware/Mirai/get_random_ip.patch'
    if 'mirai' in args.stages:
        text = patch.read_text()
        if not all(value in text for value in ('o1 = 192', 'o2 = 168', 'o3 < 16', 'o3 >= 32')):
            raise SystemExit('No se reconoce el parche de escaneo acotado del laboratorio.')
        report['scanner_patch_sha256'] = hashlib.sha256(patch.read_bytes()).hexdigest()
    # Inspección de TODOS los contenedores actuales, sin incluir respaldos renombrados.
    for node in nodes.values():
        if node['node_type'] != 'docker':
            continue
        name = 'GNS3.' + node['name'] + '.' + project['project_id']
        c = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
        if (not c['Config'].get('NetworkDisabled') or
                c['NetworkSettings'].get('Networks') or
                c['HostConfig'].get('NetworkMode') == 'host'):
            raise SystemExit('Revisar conexión Docker externa de ' + name)
    print('Comprobaciones previas completadas. Evidencias:', output, flush=True)
    if args.check_only:
        print('Solo consulta: no se ejecutaron etapas.')
        return

    groups = {
        'mirai': ['iotsim-mirai-cnc-1', 'iotsim-mirai-scan-listener-1',
                  'iotsim-mirai-wget-loader-1', 'iotsim-mirai-loader-1', 'iotsim-mirai-bot-1'],
        'merlin': ['iotsim-merlin-cnc-1'],
        'mqtt': ['iotsim-metasploit-1'],
    }
    scripts = {'mirai': 'run_mirai.py', 'merlin': '../replication/md_run_merlin.py', 'mqtt': 'run_metasploit.py'}
    cleanup_errors = []
    for stage in dict.fromkeys(args.stages):
        folder = output / stage
        folder.mkdir()
        state = {'start_utc': utc(), 'status': 'pending', 'behavior_validated': False}
        report['stages'][stage] = state
        started, captures = [], []
        try:
            targets = list(groups[stage])
            if stage == 'merlin':
                compromised = [n['name'] for n in nodes.values() if 'compromised' in n['name']]
                if False:
                    raise RuntimeError('El original exige un nodo compromised único; '
                                       f'encontrados {len(compromised)}. No se eligió otro dispositivo.')
                targets += compromised
            for name in targets:
                if name not in nodes:
                    raise RuntimeError('Falta el nodo ' + name)
                if name in groups[stage] and nodes[name]['status'] == 'started':
                    raise RuntimeError('El nodo de ataque ya estaba activo; detenerlo antes de una nueva corrida: ' + name)
            # No mezclar evidencia con capturas anteriores.
            links = api(path + '/links')
            for name in targets:
                node = nodes[name]
                matches = [link for link in links if any(
                    e['node_id'] == node['node_id'] and e['adapter_number'] == 0
                    and e['port_number'] == 0 for e in link['nodes'])]
                if len(matches) != 1 or matches[0].get('capturing'):
                    raise RuntimeError('Revisar enlace/captura previa de ' + name)
            for name in targets:
                node = nodes[name]
                api(path + '/nodes/' + node['node_id'] + '/start', 'POST')
                started.append(node)
                link = next(link for link in links if any(
                    e['node_id'] == node['node_id'] and e['adapter_number'] == 0
                    and e['port_number'] == 0 for e in link['nodes']))
                filename = f'{stage}-{name}-{stamp}.pcap'
                api(path + '/links/' + link['link_id'] + '/start_capture', 'POST',
                    {'capture_file_name': filename})
                captures.append({'node': name, 'link_id': link['link_id'],
                                 'pcap': str(Path(project['path']) / 'project-files/captures' / filename)})
                (folder / 'captures.json').write_text(json.dumps(captures, indent=2))
            print(stage + ': esperando servicios (30 s)...', flush=True)
            time.sleep(30)
            original = repo / 'src' / scripts[stage]
            state['source_sha256'] = hashlib.sha256(original.read_bytes()).hexdigest()
            if stage == 'mirai':
                bot_name = 'GNS3.iotsim-mirai-bot-1.' + project['project_id']
                subprocess.run(['docker', 'update', '--memory', '512m', '--memory-swap', '-1',
                                '--cpuset-cpus', '0', '--cpu-period', '100000',
                                '--cpu-quota', '10000', bot_name], check=True, stdout=subprocess.DEVNULL)
            state['launcher_start_utc'] = utc()
            state['launcher_exit_code'] = command([str(python), '-u', str(original)],
                                                  folder / 'launcher.log')
            if state['launcher_exit_code']:
                raise RuntimeError('Lanzador con error; revisar launcher.log')
            for elapsed in range(0, args.observe_seconds, 30):
                time.sleep(min(30, args.observe_seconds - elapsed))
                print(f'{stage}: {min(elapsed + 30, args.observe_seconds)}/{args.observe_seconds} s', flush=True)
            state['status'] = 'executed_requires_evidence_review'
        except Exception as error:
            state['status'] = 'blocked_or_failed'
            state['error'] = repr(error)
            print(stage + ': ' + str(error), flush=True)
        finally:
            # Detener nodos iniciados aquí; no apagar infraestructura base.
            for node in reversed(started):
                name = 'GNS3.' + node['name'] + '.' + project['project_id']
                try:
                    command(['docker', 'logs', '--since', state['start_utc'], name],
                            folder / (node['name'] + '.log'))
                except Exception as error:
                    cleanup_errors.append('Logs ' + node['name'] + ': ' + repr(error))
                try:
                    api(path + '/nodes/' + node['node_id'] + '/stop', 'POST')
                except Exception as error:
                    cleanup_errors.append(node['name'] + ': ' + repr(error))
            for capture in captures:
                try:
                    link_path = path + '/links/' + capture['link_id']
                    if api(link_path).get('capturing'):
                        api(link_path + '/stop_capture', 'POST')
                    pcap = Path(capture['pcap'])
                    digest = hashlib.sha256()
                    with pcap.open('rb') as file:
                        for chunk in iter(lambda: file.read(1024 * 1024), b''):
                            digest.update(chunk)
                    capture['sha256'] = digest.hexdigest()
                    for suffix, cmd in (
                        ('summary', ['capinfos', '-M', '-c', '-a', '-e', '-u', str(pcap)]),
                        ('tcp', ['tshark', '-n', '-r', str(pcap), '-q', '-z', 'conv,tcp'])):
                        capture[suffix + '_exit_code'] = command(cmd, folder / (capture['node'] + '.' + suffix + '.txt'))
                except Exception as error:
                    capture['error'] = repr(error)
            (folder / 'captures.json').write_text(json.dumps(captures, indent=2))
            if stage == 'mirai':
                listener = folder / 'iotsim-mirai-scan-listener-1.log'
                rows = re.findall(r'(?m)^(192\.168\.\d+\.\d+):23\s+\S+:\S+',
                                  listener.read_text() if listener.exists() else '')
                state['listener_reports'] = len(rows)
                state['listener_unique_ips'] = sorted(set(rows))
                state['evidence_note'] = 'Reportes del listener; no prueban propagación ni DDoS.'
            state['end_utc'] = utc()
            report['cleanup_errors'] = cleanup_errors
            (output / 'report.json').write_text(json.dumps(report, indent=2))
    report['end_utc'] = utc()
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    lines = ['RESULTADOS DEL ESCENARIO', 'Directorio: ' + str(output), '']
    for stage, state in report['stages'].items():
        lines.append(stage.upper() + ': ' + state['status'])
        if 'error' in state:
            lines.append('  ' + state['error'])
        if stage == 'mirai':
            lines.append(f"  Reportes: {state.get('listener_reports', 0)}; "
                         f"IP únicas: {len(state.get('listener_unique_ips', []))}")
    lines += ['', 'No ejecutado por este lanzador: Nmap/Masscan y amplificación CoAP.',
              'La ejecución sin errores NO equivale a validación del comportamiento.',
              report['warning']]
    if cleanup_errors:
        lines += ['ERRORES DE PARADA:'] + cleanup_errors
    summary = '\n'.join(lines) + '\n'
    (output / 'RESUMEN.txt').write_text(summary)
    print('\n' + summary)
    return 1 if cleanup_errors or any(s['status'] == 'blocked_or_failed'
                                     for s in report['stages'].values()) else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Interrumpido. Revisa el informe y confirma la parada en GNS3.', file=sys.stderr)
        sys.exit(130)
