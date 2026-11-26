import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from contextlib import closing

from host import run_job


def execute(db, job):
    key = job["id"]
    if not isinstance(key, str) or not key.strip() or len(key) > 160:
        raise ValueError("job ID must contain 1 to 160 characters")
    encoded = json.dumps(job, allow_nan=False, sort_keys=True)
    with db:
        db.execute("""CREATE TABLE IF NOT EXISTS job (
            id TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT)""")
        new = db.execute("INSERT INTO job VALUES (?, ?, NULL) ON CONFLICT(id) DO NOTHING", (key, encoded))
        if not new.rowcount:
            original, response = db.execute("SELECT request, response FROM job WHERE id=?", (key,)).fetchone()
            if original != encoded:
                raise ValueError("job ID has already been used with different parameters")
            if response is None:
                raise ValueError("job already started and has no final report")
            return json.loads(response)
    try:
        report = run_job(job)
        report["experiment"]["host"] = socket.gethostname()
        result = {"ok": True, "record": report}
    except (ValueError, RuntimeError, OSError) as error:
        result = {"ok": False, "id": key, "error": str(error)}
    with db:
        db.execute("UPDATE job SET response=? WHERE id=?", (json.dumps(result, allow_nan=False), key))
    return result


def main():
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "cloudpathfi"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        data = sys.stdin.buffer.read(16_385)
        if len(data) > 16_384:
            raise ValueError("job is too large")
        with closing(sqlite3.connect(state / "jobs.sqlite3", timeout=30)) as db:
            result = execute(db, json.loads(data))
        print(json.dumps(result, allow_nan=False))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
