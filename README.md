<!-- gotham-academic-replication -->
# Replicación académica de Gotham Testbed

Este proyecto adapta la implementación publicada por X. Sáez-de-Cámara,
J. L. Flores, C. Arellano, A. Urbieta y U. Zurutuza para ejecutar su
escenario de tráfico IoT normal en una instancia OCI Ubuntu x86-64.
La documentación original se conserva a continuación.

## Alcance y resultados

- Topología de 140 nodos y 140 enlaces desplegada mediante GNS3.
- Corrida normal con 120 contenedores activos y diez routers VyOS/QEMU.
  Diez nodos de ataque quedan excluidos en esta corrida.
- Captura de 3600,005968 segundos con 2.651.026 paquetes.
- PCAP de 3.369.057.379 bytes. Los archivos de tráfico se conservan fuera
  de GitHub por su tamaño. Su huella y los informes están en evidence/.
- Mirai quedó fallido y pendiente de corrección. Merlin, MQTT/CoAP ofensivo
  y las evaluaciones de CPU, enlaces y memoria siguen pendientes.

## Archivos de la replicación

- [Procedimiento y decisiones](replication/README.txt).
- [Constructor adaptado a servidor](src/md_create_topology_headless.py).
- [Arranque del escenario normal](src/md_run_baseline_gotham.py).
- [Captura supervisada de 60 minutos](replication/md_capture_baseline.py).
- [Análisis de PCAP](replication/md_analyze_baseline.sh).
- [Evidencias de la corrida](replication/evidence/).

El supervisor se reconstruyó a partir del bloque de terminal usado durante
el experimento. Incluye mejoras de registro y aún requiere una nueva
ejecución de validación como archivo independiente. Los informes históricos
corresponden a la corrida original del 18 de noviembre de 2026.

## Comparación con la tabla V

Porcentajes de paquetes sobre un total de 2.651.026 tramas. Se toman las
primeras ramas de la jerarquía de TShark, sin sumar apariciones anidadas.

| Protocolo | Autores (%) | Réplica (%) |
|---|---:|---:|
| RTP | 87,638 | 88,028 |
| MQTT | 2,581 | 2,561 |
| TLS | 1,728 | 1,757 |
| DNS | 1,533 | 1,474 |
| NTP | 0,278 | 0,253 |
| RTCP | 0,265 | 0,252 |
| CoAP | 0,121 | 0,058 |
| DTLS | 0,180 | 0,170 |

La disección usa TShark 3.6.2 con `--enable-heuristic rtp_udp`.
La clasificación RTP requiere validación de los flujos. La similitud de
porcentajes no establece equivalencia de rendimiento ni de toda la evaluación.

## Cambios respecto a la implementación publicada

- Ejecución del constructor sin abrir ventanas Konsole.
- Lanzador específico para observar tráfico normal sin nodos de ataque.
- Binario RTSP oficial v0.18.3 en lugar de la etiqueta Docker ausente.
- Inicio de Open vSwitch con `/etc/openvswitch/init.sh`.
- Open vSwitch 2.17.12 frente a 2.12.3 documentado en el artículo.
- `auto_close=False` para evitar el cierre al desconectarse el visor.

## Fuente y atribución

Artículo: *Gotham Testbed: A Reproducible IoT Testbed for Security Experiments
and Dataset Generation*, IEEE TDSC 21(1), 186–203, 2024.
[DOI](https://doi.org/10.1109/TDSC.2023.3247166).
[Repositorio original](https://github.com/xsaga/gotham-iot-testbed).
Commit base `8881f43a385cec56014caa50898a88c66e6b191b`.
Se conservan las atribuciones y licencias originales.

---

## Documentación original de los autores

# Gotham Testbed: A Reproducible IoT Testbed for Security Experiments and Dataset Generation


This repository contains the source code and implementation of the emulated testbed described in the following paper (open access):

X. Sáez-de-Cámara, J. L. Flores, C. Arellano, A. Urbieta and U. Zurutuza, "Gotham Testbed: A Reproducible IoT Testbed for Security Experiments and Dataset Generation," in IEEE Transactions on Dependable and Secure Computing, doi: [10.1109/TDSC.2023.3247166](https://doi.org/10.1109/TDSC.2023.3247166).

If you use or build upon this testbed, please consider citing the article.

Tested on Ubuntu 20.04.4 LTS and 22.04 LTS

---

## Dependencies

- make

- wget

- konsole (some scripts assume that the konsole terminal emulator is installed)

- Python 3

- Docker: https://docs.docker.com/engine/install/

- GNS3: https://www.gns3.com/, https://docs.gns3.com/docs/getting-started/installation/linux
    - Answer 'Yes' when the Wireshark installer asks 'Should non-superusers be able to capture packets?'

## Prerequisites

- Your user should belong to the following groups: ubridge, libvirt, kvm, wireshark, docker. `sudo usermod -aG ubridge,libvirt,kvm,wireshark,docker $USER`. Restart the machine.


- For large topologies with many nodes (containers, VMs) you might need to increase the maximum number of open file descriptors (in the machine running GNS3) to start all the nodes simultaneously. Check the current limit with `ulimit -n`

- KVM virtualization support. When running GNS3 in a virtual machine, enable nested virtualization.

---

## Python virtual environment

Create a Python virtual environment to install the Python dependencies of the project (You might need to install the `python3-venv` package). To interact with the project, activate the virtual environment.

Inside the project's repository directory, run:

```
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt
```

## Template creation

### Build Docker images

All the Dockerfiles and the dependencies that describe the emulated nodes (IoT devices, servers, attackers) are inside the `./Dockerfiles` directory. The build process of some Docker images depend on other images; instead of building them manually, the project includes a `Makefile` to automate the process.

Run `make` to automatically build all the Docker images in the correct order:
```
$ make
```

This can take a long time (approx 30 min depending on the host and network speed); you can parallelize the build process running make with the `-j` flag.

If you modify any Dockerfile, configuration file, program or any other file inside the `./Dockerfiles` directory, run `make` again. It will rebuild the updated images and other images that depend on them.

### Docker template creation

Open GNS3, the GNS3 server must be running.
Inside the `./src` directory run:
```
(venv) $ python3 create_templates.py
```

You can verify the created templates in GNS3 select: Edit > Preferences > Docker containers

![gns3 templates](img/gns3_templates.png)

### Create router template

Inside the project's repository directory, run:

```
make vyosiso
```

The artifacts (a .iso file and a .qcow2 file) will be downloaded into the `~/Downloads directory`. Follow the instructions to import appliances in GNS3 https://docs.gns3.com/docs/using-gns3/beginners/import-gns3-appliance/. The router appliance file is located at `./router/iotsim-vyos.gns3a`.

![gns3 install vyos appliance](img/gns3_installvyosappliance.png)

## Topology builder

GNS3 must be running.
Inside the `./src` directory run:
```
(venv) $ python3 create_topology_gotham.py
```

![gns3 topology](img/gns3_topology.png)

## Scenario generator

GNS3 must be running.
Inside the `src/` directory run:
```
(venv) $ python3 run_scenario_gotham.py
```
