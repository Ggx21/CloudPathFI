import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess

from storage import save


def dispatch(host, directory, job):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", host):
        raise ValueError("expected an SSH host alias")
    if not directory.startswith("/"):
        raise ValueError("the remote project directory must be absolute")
    remote = f"cd {shlex.quote(directory)} && exec python3 -m control.worker"
    run = subprocess.run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                          "-o", "ConnectTimeout=10", host, remote], input=json.dumps(job, allow_nan=False),
                         encoding="utf-8", stdout=subprocess.PIPE, timeout=180, check=True)
    response = json.loads(run.stdout)
    if not response["ok"]:
        raise ValueError(f"{host}: {response['error']}")
    record = response["record"]
    if record["experiment"]["id"] != job["id"] or record["fault"]["model"] != job["model"]:
        raise ValueError("worker returned another job's report")
    return record


def main():
    parser = argparse.ArgumentParser(description="Dispatch a private-namespace measurement to a host worker.")
    parser.add_argument("host", help="host alias from SSH configuration")
    parser.add_argument("job", type=Path, help="JSON with id, model and model parameters")
    parser.add_argument("--directory", required=True, help="absolute repository path on the worker")
    parser.add_argument("--database", required=True, type=Path, help="controller result database")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8-sig"))
        record = dispatch(args.host, args.directory, job)
        with closing(sqlite3.connect(args.database)) as db:
            print(save(db, record))
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
