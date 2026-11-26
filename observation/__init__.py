"""Register evidence from experiments applied and observed outside CloudPathFI."""

from datetime import datetime
import math

from storage import save
from topology import resolve_path, target_index
from .evidence import check_evidence


PHASES = ("before", "during", "after")
RECOVERY = ("recovered", "partial", "unrecovered", "unknown")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _timestamp(value):
    date = datetime.fromisoformat(_text(value, "observed_at").replace("Z", "+00:00"))
    if date.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return date


def _samples(reading):
    pairs = reading["samples"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("metric samples must contain [duration_s, value] pairs")
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each sample must contain duration_s and value")
        if not all(type(v) in (int, float) and math.isfinite(v) for v in pair):
            raise ValueError("sample durations and values must be finite numbers")
        if pair[0] <= 0 or pair[1] < 0:
            raise ValueError("sample durations must be positive and values nonnegative")
    return pairs


def _weighted_mean(samples):
    return sum(seconds * value for seconds, value in samples) / sum(seconds for seconds, _ in samples)


def _metrics(phases):
    readings = [phase.get("metrics", {}) for phase in phases]
    if any(not isinstance(group, dict) for group in readings):
        raise ValueError("metrics must be an object keyed by metric name")
    measured, unscored = [], {}
    for name in sorted(set().union(*readings)):
        _text(name, "metric name")
        groups = [group[name] for group in readings if name in group]
        if any(not isinstance(group, dict) for group in groups):
            raise ValueError(f"{name}: each phase measurement must be an object")
        intervals = [_samples(group) for group in groups]
        if len(groups) != len(PHASES):
            unscored[name] = "missing phase measurements"
            continue
        first = groups[0]
        direction = first.get("direction")
        if direction not in ("higher_is_worse", "lower_is_worse"):
            raise ValueError(f"{name}: baseline must specify direction")
        if any(group.get("direction", direction) != direction for group in groups):
            raise ValueError(f"{name}: measurement direction differs between phases")
        baseline = _weighted_mean(intervals[0])
        sigma = first.get("baseline_sigma")
        if sigma is None:
            if len(intervals[0]) == 1:
                unscored[name] = "a single baseline reading needs measured baseline_sigma"
                continue
            variance = _weighted_mean([(seconds, (value - baseline) ** 2) for seconds, value in intervals[0]])
            sigma = math.sqrt(variance)
        if baseline == 0 and not first.get("scale"):
            unscored[name] = "zero baseline needs a positive normalization scale"
            continue
        metric = {"name": name, "direction": direction, "weight": first.get("weight", 1),
                  "baseline": baseline, "baseline_sigma": sigma, "observed": _weighted_mean(intervals[1]),
                  "intervals": [pair for group in intervals for pair in group]}
        if "scale" in first:
            metric["scale"] = first["scale"]
        measured.append(metric)
    return measured, unscored


def build_record(run_id, phase_records, *, model, path, target, recovery, occurrence=1, parameters=None):
    _text(run_id, "run ID")
    path = resolve_path(path)
    target_index(path, target, occurrence)
    if recovery not in RECOVERY:
        raise ValueError(f"invalid reported recovery state: {recovery}")
    if parameters is not None and not isinstance(parameters, dict):
        raise ValueError("fault parameters must be a JSON object")
    by_phase = {}
    for record in phase_records:
        if not isinstance(record, dict) or record.get("id") != run_id:
            raise ValueError("each phase record must carry the requested run ID")
        phase = record.get("phase")
        if phase not in PHASES or phase in by_phase:
            raise ValueError("expected one record each for before, during and after")
        _text(record.get("source"), "source")
        _timestamp(record.get("observed_at"))
        evidence = record.get("evidence", {})
        check_evidence(model, evidence, required=phase == "during")
        if not (evidence or record.get("metrics") or record.get("linux_counters")):
            raise ValueError(f"{phase} must include evidence, measurements or captured Linux counters")
        by_phase[phase] = record
    if set(by_phase) != set(PHASES):
        raise ValueError("all three phases are required")
    phases = [by_phase[name] for name in PHASES]
    times = [_timestamp(phase["observed_at"]) for phase in phases]
    if times != sorted(times):
        raise ValueError("phase observation times are out of order")
    metrics, unscored = _metrics(phases)
    return {"experiment": {"id": run_id, "status": "recorded", "backend": "external-observation"},
            "fault": {"model": model, "target": target, "occurrence": occurrence,
                      "parameters": parameters or {}, "application": "external", "reported_recovery": recovery},
            "path": path, "phases": by_phase, "unscored_metrics": unscored,
            "observations": [{"hop": target, "occurrence": occurrence, "metrics": metrics}] if metrics else []}


def register(db, run_id, phase_records, **details):
    return save(db, build_record(run_id, phase_records, **details))
