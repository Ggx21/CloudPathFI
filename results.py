import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from storage import coverage, fetch, history, save

def main():
    parser = argparse.ArgumentParser(description="Store and query CloudPathFI experiment results.")
    commands = parser.add_subparsers(dest="command", required=True)
    put = commands.add_parser("put", help="save a completed or failed run")
    put.add_argument("database", type=Path)
    put.add_argument("record", type=Path, help="experiment JSON")
    get = commands.add_parser("get", help="retrieve a run and its per-hop scores")
    get.add_argument("database", type=Path)
    get.add_argument("id")
    hops = commands.add_parser("history", help="show recorded scores for one hop")
    hops.add_argument("database", type=Path)
    hops.add_argument("hop")
    report = commands.add_parser("coverage", help="count recorded runs, targets and path/model pairs")
    report.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "put":
            record = json.loads(args.record.read_text(encoding="utf-8-sig"))
            with closing(sqlite3.connect(args.database)) as db:
                answer = {"id": save(db, record)}
        else:
            uri = args.database.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as db:
                if args.command == "coverage":
                    answer = coverage(db)
                elif args.command == "get":
                    answer = fetch(db, args.id)
                else:
                    answer = history(db, args.hop)
        print(json.dumps(answer, indent=2, allow_nan=False))
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, OverflowError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
