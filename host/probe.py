"""Private measurement process. Its only network interface must be an isolated loopback."""

from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
import shutil
import socket
from statistics import mean, pstdev
import subprocess
import sys
import time


PROBES_PER_PHASE = 8
SLOT_S = 0.35
TIMEOUT_S = 0.30
LOOPBACK = "127.0.0.1"
HOP = "netns.lo"


def validate_job(job):
    if not isinstance(job, dict) or job.get("model") not in ("FM-07", "FM-08"):
        raise ValueError("the host backend accepts FM-07 and FM-08")
    parameter = "loss_pct" if job["model"] == "FM-07" else "delay_ms"
    if set(job) != {"id", "model", parameter}:
        raise ValueError(f"expected exactly id, model and {parameter}")
    if not isinstance(job["id"], str) or not job["id"].strip() or len(job["id"]) > 128:
        raise ValueError("experiment ID must be nonempty and at most 128 characters")
    value = job[parameter]
    if type(value) not in (float, int) or not 0 <= value <= 100 or not math.isfinite(value):
        raise ValueError(f"{parameter} must be a finite number between 0 and 100")
    return dict(job)


def system_tool(name):
    path = shutil.which(name, path="/usr/sbin:/usr/bin:/sbin:/bin")
    if path is None:
        raise RuntimeError(f"required Linux tool is missing: {name}")
    return path


def _configure(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "could not configure the isolated loopback")


def _receive(sock, expected, deadline):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        sock.settimeout(remaining)
        try:
            if sock.recv(64) == expected:
                return True
        except socket.timeout:
            return False


def _phase(client, echo, name, start):
    rows = []
    for sequence in range(PROBES_PER_PHASE):
        payload = f"{name}/{sequence}".encode("ascii")
        sent = time.monotonic()
        deadline = sent + TIMEOUT_S
        client.send(payload)
        rtt = None
        if _receive(echo, payload, deadline):
            echo.send(payload)
            if _receive(client, payload, deadline):
                rtt = (time.monotonic() - sent) * 1000
        # Fixed observation slots give a timeout the same sampling weight as a fast reply.
        time.sleep(max(0, sent + SLOT_S - time.monotonic()))
        rows.append({"phase": name, "sequence": sequence + 1, "sent_ms": (sent - start) * 1000,
                     "delivered": rtt is not None, "rtt_ms": rtt,
                     "sample_seconds": time.monotonic() - sent})
    return rows


def _summary(rows):
    rtts = [r["rtt_ms"] for r in rows if r["delivered"]]
    return {"sent": len(rows), "delivered": len(rtts), "lost": len(rows) - len(rtts),
            "delivery_fraction": len(rtts) / len(rows), "mean_rtt_ms": mean(rtts) if rtts else None}


def _metric(name, direction, values, groups, rows):
    before = values[:len(groups["before"])]
    during = values[len(before):len(before) + len(groups["during"])]
    return {"name": name, "direction": direction, "weight": 1, "baseline": mean(before),
            "baseline_sigma": pstdev(before), "observed": mean(during),
            "intervals": [[row["sample_seconds"], value] for row, value in zip(rows, values)]}


def measure(job, launcher_namespace_fd):
    # Close the inherited descriptor as soon as we have compared namespace identities.
    try:
        if not os.readlink(f"/proc/self/fd/{launcher_namespace_fd}").startswith("net:["):
            raise RuntimeError("invalid launcher network namespace descriptor")
        same_namespace = os.path.samestat(os.fstat(launcher_namespace_fd), os.stat("/proc/self/ns/net"))
    finally:
        os.close(launcher_namespace_fd)
    if same_namespace:
        raise RuntimeError("the worker requires a fresh network namespace")
    if [name for _, name in socket.if_nameindex()] != ["lo"]:
        raise RuntimeError("the namespace must contain exactly the loopback interface")
    ip = system_tool("ip")
    tc = system_tool("tc")
    _configure([ip, "link", "set", "lo", "up"])
    model = job["model"]
    parameter, action, unit = ("loss_pct", "loss", "%") if model == "FM-07" else ("delay_ms", "delay", "ms")
    amount = format(Decimal(str(job[parameter])), "f") + unit
    groups = {}
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as echo, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        echo.bind((LOOPBACK, 0))
        client.bind((LOOPBACK, 0))
        client.connect(echo.getsockname())
        echo.connect(client.getsockname())
        groups["before"] = _phase(client, echo, "before", start)
        if not any(row["delivered"] for row in groups["before"]):
            raise RuntimeError("no UDP echo succeeded during the baseline")
        _configure([tc, "qdisc", "add", "dev", "lo", "root", "netem", action, amount])
        try:
            injected_ms = (time.monotonic() - start) * 1000
            groups["during"] = _phase(client, echo, "during", start)
        finally:
            _configure([tc, "qdisc", "del", "dev", "lo", "root"])
        recovered_ms = (time.monotonic() - start) * 1000
        groups["after"] = _phase(client, echo, "after", start)
    ended_ms = (time.monotonic() - start) * 1000
    rows = [row for group in groups.values() for row in group]
    metrics = [_metric("udp_echo_delivery_fraction", "lower_is_worse",
                       [int(row["delivered"]) for row in rows], groups, rows)]
    # A timed-out echo has no measured RTT. Preserve partial RTTs in the packet log.
    if model == "FM-08" and all(row["delivered"] for row in rows):
        metrics.append(_metric("udp_echo_rtt_ms", "higher_is_worse", [row["rtt_ms"] for row in rows], groups, rows))
    return {
        "experiment": {"id": job["id"], "status": "completed", "backend": "linux-netns-udp",
                       "started_at": started_at, "clock": "monotonic_ms", "completed_ms": ended_ms},
        "fault": {"model": model, "target": HOP, "parameters": {parameter: job[parameter]},
                  "injected_ms": injected_ms, "recovered_ms": recovered_ms, "status": "removed",
                  "scope": "loopback egress for both the UDP request and the reply"},
        "path": ["udp-client", HOP, "udp-echo"],
        "settings": {"probes_per_phase": PROBES_PER_PHASE, "slot_s": SLOT_S, "timeout_s": TIMEOUT_S},
        "packets": rows, "summary": {name: _summary(group) for name, group in groups.items()},
        "observations": [{"hop": HOP, "metrics": metrics, "anomalies": [],
                          "propagation": {"weight": 0, "score": 0}}],
    }


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("the measurement process must be launched by host.run_job")
        job = validate_job(json.load(sys.stdin))
        print(json.dumps(measure(job, int(sys.argv[1])), allow_nan=False))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
