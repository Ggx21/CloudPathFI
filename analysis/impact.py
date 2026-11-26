from topology import FAULT_MODELS, resolve_path, target_index

from .metrics import metric_impact, number


def distinct(rows, field):
    seen = set()
    for row in rows:
        key = row[field]
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise ValueError(f"invalid or duplicate {field}: {key!r}")
        seen.add(key)
        yield row


def propagation_score(data):
    if "score" in data:
        return number(data["score"], "propagation score")
    # Each reported service contributes once, even when several traces link it to this run.
    downstream = distinct(data["affected_direct_services"], "service")
    services = data["critical_services_with_linked_anomalies"]
    if not isinstance(services, list) or not all(isinstance(s, str) and s.strip() for s in services):
        raise ValueError("critical_services_with_linked_anomalies must list service names")
    critical = set(services)
    return sum(number(s["criticality"], "service criticality") for s in downstream) + len(critical)


def analyze(record):
    path = list(resolve_path(record["path"]))
    if "fault" in record and record["fault"]["model"] not in FAULT_MODELS:
        raise ValueError(f"unknown fault model: {record['fault']['model']}")
    observations = []
    positions = set()
    for row in record["observations"]:
        hop = row["hop"]
        occurrence = row.get("occurrence", 1)
        position = target_index(path, hop, occurrence)
        if position in positions:
            raise ValueError(f"duplicate observation for {hop} visit {occurrence}")
        positions.add(position)
        metrics = [metric_impact(m) for m in distinct(row["metrics"], "name")]
        anomalies = sum(number(a["weight"], "anomaly weight") * number(a["severity"], "severity")
                        for a in distinct(row.get("anomalies", []), "id"))
        p = row.get("propagation")
        propagation = number(p["weight"], "propagation weight") * propagation_score(p) if p else 0
        score = sum(m["contribution"] for m in metrics) + anomalies + propagation
        observations.append({"hop": hop, "occurrence": occurrence, "metrics": metrics,
                             "anomaly_contribution": anomalies, "propagation_contribution": propagation,
                             "impact_score": score})
    return {"path": path, "observations": observations}
