import json
from collections import Counter

from analysis import analyze
from topology import resolve_path, target_index


def save(db, record):
    experiment, fault = record["experiment"], record["fault"]
    key, status = experiment["id"], experiment["status"]
    model, target = fault["model"], fault["target"]
    if not all(isinstance(s, str) and s.strip() for s in (key, status, model, target)):
        raise ValueError("missing experiment ID, status, model or target")
    result = analyze(record)
    target_index(result["path"], target, fault.get("occurrence", 1))
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False, sort_keys=True)
    with db:
        db.execute("""CREATE TABLE IF NOT EXISTS experiment (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, model TEXT NOT NULL, record TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS impact_by_visit (
            experiment_id TEXT NOT NULL REFERENCES experiment(id), hop TEXT NOT NULL, visit INTEGER NOT NULL,
            score REAL NOT NULL, details TEXT NOT NULL, PRIMARY KEY (experiment_id, hop, visit))""")
        added = db.execute("INSERT INTO experiment VALUES (?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                           (key, status, model, payload))
        if added.rowcount == 0:
            existing = db.execute("SELECT record FROM experiment WHERE id = ?", (key,)).fetchone()
            if existing[0] != payload:
                raise ValueError(f"experiment {key!r} already has a different record")
            return key
        for row in result["observations"]:
            db.execute("INSERT INTO impact_by_visit VALUES (?, ?, ?, ?, ?)",
                       (key, row["hop"], row["occurrence"], row["impact_score"], json.dumps(row, allow_nan=False)))
    return key


def scores(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    parts = []
    if "impact" in tables:
        parts.append("SELECT experiment_id, hop, 1 AS visit, score, details FROM impact")
    if "impact_by_visit" in tables:
        parts.append("SELECT experiment_id, hop, visit, score, details FROM impact_by_visit")
    if not parts:
        raise ValueError("no recorded impact scores in this database")
    return " UNION ALL ".join(parts)


def fetch(db, key):
    row = db.execute("SELECT record FROM experiment WHERE id = ?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"unknown experiment: {key}")
    rows = db.execute(f"SELECT details FROM ({scores(db)}) WHERE experiment_id = ? ORDER BY hop, visit", (key,))
    return {"record": json.loads(row[0]), "impact": [json.loads(details) for details, in rows]}


def history(db, hop):
    rows = db.execute(f"""SELECT e.id, e.status, e.model, i.visit, i.score FROM experiment AS e
        JOIN ({scores(db)}) AS i ON e.id = i.experiment_id WHERE i.hop = ? ORDER BY e.rowid, i.visit""", (hop,))
    return [dict(zip(("id", "status", "model", "occurrence", "impact_score"), row)) for row in rows]


def coverage(db):
    models, states = Counter(), Counter()
    scenarios, targets = set(), set()
    for model, status, raw in db.execute("SELECT model, status, record FROM experiment"):
        record = json.loads(raw)
        path = tuple(resolve_path(record["path"]))
        target = record["fault"]
        states[status] += 1
        models[model] += 1
        scenarios.add((path, model))
        targets.add((path, target["target"], target.get("occurrence", 1)))
    return {"runs": sum(states.values()), "by_status": states, "by_model": models,
            "distinct_path_model_pairs": len(scenarios), "distinct_path_positions_targeted": len(targets)}
