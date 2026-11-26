"""Take a read-only snapshot of counters exposed to this Linux process."""

from datetime import datetime, timezone
from pathlib import Path
import socket
import sys


def snapshot():
    if not sys.platform.startswith("linux"):
        raise ValueError("local /proc counter capture requires Linux")
    observed_at = datetime.now(timezone.utc).isoformat()
    cpu = Path("/proc/stat").read_text().splitlines()[0].split()
    cpu_fields = "user nice system idle iowait irq softirq steal guest guest_nice".split()
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable", "MemFree"):
            memory[key] = int(value.split()[0])
    columns = ("rx_bytes rx_packets rx_errors rx_dropped rx_fifo rx_frame rx_compressed rx_multicast "
               "tx_bytes tx_packets tx_errors tx_dropped tx_fifo tx_collisions tx_carrier tx_compressed").split()
    interfaces = {}
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, counts = line.rsplit(":", 1)
        interfaces[name.strip()] = dict(zip(columns, map(int, counts.split())))
    return {"host": socket.gethostname(), "observed_at": observed_at,
            "cpu_ticks": dict(zip(cpu_fields, map(int, cpu[1:]))),
            "memory_kib": memory, "interfaces": interfaces}
