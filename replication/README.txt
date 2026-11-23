Gotham Testbed: replicación del escenario de tráfico normal en OCI

Código original: https://github.com/xsaga/gotham-iot-testbed
Commit usado: 8881f43a385cec56014caa50898a88c66e6b191b
Artículo: DOI 10.1109/TDSC.2023.3247166, tabla V.

Ejecutar desde la raíz del repositorio, en una sesión tmux:
  cd src
  ../.venv/bin/python -u md_run_baseline_gotham.py
  cd ..
  .venv/bin/python -u replication/md_capture_baseline.py
  bash replication/md_analyze_baseline.sh

La captura requiere gns3server activo en 127.0.0.1:3080, proyecto abierto,
auto_close=False y extremos del enlace RNORTH eth0 encendidos.
El arranque del escenario se realiza con md_run_baseline_gotham.py.
md_capture_baseline.py solo realiza y supervisa la captura.
Los resultados e incidencias se registran en replication/results/.
Los PCAP permanecen en la carpeta de capturas de GNS3, fuera del repositorio.
El análisis admite una ruta alternativa como primer argumento.

Procedencia del código:
El supervisor de captura se reconstruyó a partir del bloque de terminal
usado en la corrida exitosa. Se añadieron localización dinámica del proyecto
y enlace, registro por minuto y manejo de errores. Este archivo no existía
como .py cuando se obtuvo el PCAP del 18 de noviembre de 2026.
El análisis reproduce los comandos utilizados en aquella corrida.

Cambios de implementación:
- Constructor sin ventanas Konsole, en src/md_create_topology_headless.py.
- Corrida normal con diez nodos de ataque excluidos del arranque.
- RTSP v0.18.3 obtenido del binario oficial al faltar el tag Docker original.
- Inicio de Open vSwitch mediante /etc/openvswitch/init.sh.
- Open vSwitch observado 2.17.12; el artículo documenta 2.12.3.
- TShark observado 3.6.2, con --enable-heuristic rtp_udp para el análisis.

Resultado confirmado de la corrida del 18 de noviembre de 2026:
PCAP gotham-normal-60min-20261118T212627Z.pcap
2651026 paquetes, 3369057379 bytes, 3600.005968 segundos.
SHA256 92b189222946e8e24b1e7ab70264f98b1d0db84af283df4b67ad015ea8a990bf
La tabla de jerarquía requiere evitar doble conteo de protocolos anidados.
La heurística RTP es parte de la configuración de disección declarada.
Las pruebas de ataques y rendimiento requieren registros adicionales.

evidence/ contiene copias de informes originales disponibles en HOME.
capture-history-*.json conserva los metadatos que se encuentren allí.
runtime.txt describe el entorno al archivar, que puede diferir del de la captura.
runtime-changes.patch conserva el diff de los scripts rastreados por Git.
Dockerfile.stream_server.used copia el Dockerfile RTSP modificado.
OVS.template.used.json conserva la plantilla actual si GNS3 está accesible.
Los scripts nuevos y los archivos originales permanecen en sus rutas.
src/md_run_baseline_gotham.py y src/md_create_topology_headless.py deben incluirse
expresamente en el commit. evidence/ registra sus huellas.
requirements-environment.txt permite identificar las dependencias Python
instaladas al archivar; se genera desde el entorno .venv existente.
El ejecutable RTSP se conserva en la VM y se excluye del commit. Su hash
se registra en evidence/rtsp-binary-sha256.txt. Se obtiene desde:
https://github.com/bluenviron/mediamtx/releases/download/v0.18.3/rtsp-simple-server_v0.18.3_linux_amd64.tar.gz
Extraer rtsp-simple-server y copiarlo a Dockerfiles/iot/stream_server/.

Mirai quedó fallido y pendiente de corregir y ejecutar con éxito, según
la confirmación del autor de esta réplica. Existe una carpeta de intento
/home/ubuntu/gotham-mirai-20261118T232523Z con completed=true, pero esa
bandera del lanzador no acredita el éxito del escenario. Los intentos y
sus registros permanecen fuera de la evidencia del escenario base.

Antes de publicar, revisar git status y seleccionar archivos explícitamente.
Los logs Mirai pueden contener credenciales del laboratorio; este archivo
de preparación no los recopila. No añadir claves SSH ni archivos .oci.
Las credenciales deliberadamente débiles del testbed deben quedar aisladas.
Conservar las licencias y la atribución del repositorio original.
