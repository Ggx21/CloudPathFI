"""Calculate synthetic probe observations on an in-process virtual clock."""

import json
import math
from hashlib import sha256
from random import Random, SystemRandom
from statistics import mean

from topology import resolve_path, target_index


def summarize(packets):
    latencies = [packet["latency_ms"] for packet in packets if packet["delivered"]]
    return {"sent": len(packets), "delivered": len(latencies),
            "lost": len(packets) - len(latencies),
            "delivery_fraction": len(latencies) / len(packets),
            "mean_latency_ms": mean(latencies) if latencies else None}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _fault_parameters(model, loss_pct, delay_ms):
    if model == "FM-07":
        loss_pct = 25 if loss_pct is None else loss_pct
        if delay_ms is not None or not _finite(loss_pct) or not 0 <= loss_pct <= 100:
            raise ValueError("FM-07 accepts a loss percentage from 0 to 100")
        return {"loss_pct": loss_pct}
    if model == "FM-08":
        delay_ms = 50 if delay_ms is None else delay_ms
        if loss_pct is not None or not _finite(delay_ms) or delay_ms < 0:
            raise ValueError("FM-08 accepts a finite nonnegative delay")
        return {"delay_ms": delay_ms}
    raise ValueError("choose FM-07 (loss) or FM-08 (delay)")


def simulate(path, hop, model, *, occurrence=1, experiment_id=None, start_ms=20,
             end_ms=60, packets=10, interval_ms=10, hop_ms=1, loss_pct=None,
             delay_ms=None, seed=0):
    """Run one local experiment. A fault is active on arrival in [start_ms, end_ms)."""
    path = resolve_path(path)
    index_in_path = target_index(path, hop, occurrence)
    if experiment_id is not None and (not isinstance(experiment_id, str) or not experiment_id.strip()):
        raise ValueError("experiment_id must be a nonempty string")
    if not all(_finite(t) for t in (start_ms, end_ms, interval_ms, hop_ms)):
        raise ValueError("the fault window and probe timing must be finite")
    if type(packets) is not int or packets < 3:
        raise ValueError("use at least three packets")
    if not (0 <= start_ms < end_ms and interval_ms > 0 and hop_ms > 0):
        raise ValueError("use 0 <= start < end and positive time steps")
    if seed is None:
        seed = SystemRandom().getrandbits(64)
    if not isinstance(seed, (str, int)) and not _finite(seed):
        raise ValueError("seed must be a finite number or a string")
    parameters = _fault_parameters(model, loss_pct, delay_ms)
    settings = {"model": model, "hop": hop, "occurrence": occurrence, "start_ms": start_ms, "end_ms": end_ms,
                "packets": packets, "interval_ms": interval_ms, "hop_ms": hop_ms,
                "seed": seed, **parameters}
    target_offset = index_in_path * hop_ms
    nominal_latency = len(path) * hop_ms
    phases = {"before": [], "during": [], "after": []}
    rng = Random(seed)
    records = []
    for index in range(packets):
        sent = index * interval_ms
        entered = sent + target_offset
        phase = "before" if entered < start_ms else "during" if entered < end_ms else "after"
        latency = nominal_latency
        if phase == "during":
            if model == "FM-08":
                latency += parameters["delay_ms"]
            elif rng.random() < parameters["loss_pct"] / 100:
                latency = None
        record = {"id": index + 1, "sent_ms": sent, "hop_arrival_ms": entered, "phase": phase,
                  "delivered": latency is not None, "latency_ms": latency,
                  "received_ms": sent + latency if latency is not None else None}
        records.append(record)
        phases[phase].append(record)

    if any(not rows for rows in phases.values()):
        raise ValueError("choose a window and packet schedule with port arrivals before, during and after the fault")
    summary = {phase: summarize(rows) for phase, rows in phases.items()}
    if model == "FM-07":
        name, direction = "delivery_fraction", "lower_is_worse"
        samples = [int(row["delivered"]) for row in records]
    else:
        name, direction = "mean_latency_ms", "higher_is_worse"
        samples = [row["latency_ms"] for row in records]
    # Each regularly scheduled probe represents one sampling interval.
    metric = {"name": name, "weight": 1, "direction": direction,
              "baseline": summary["before"][name], "observed": summary["during"][name],
              "baseline_sigma": 0, "intervals": [[interval_ms / 1000, value] for value in samples]}
    observation = {"hop": hop, "occurrence": occurrence, "metrics": [metric], "anomalies": [],
                   "propagation": {"weight": 0, "score": 0}}
    if experiment_id is None:
        # Identical simulations can be retried against the result store.
        identity = json.dumps([path, settings], sort_keys=True, allow_nan=False).encode("utf-8")
        experiment_id = "sim-" + sha256(identity).hexdigest()
    experiment = {"id": experiment_id, "status": "completed", "clock": "virtual_ms",
                  "measurement_start_ms": target_offset,
                  "measurement_end_ms": target_offset + packets * interval_ms}
    fault = {"model": model, "target": hop, "occurrence": occurrence,
             "parameters": parameters, "injected_ms": start_ms, "recovered_ms": end_ms,
             "status": "recovered"}
    return {"experiment": experiment, "fault": fault, "path": path, "settings": settings,
            "packets": records, "summary": summary, "observations": [observation]}
