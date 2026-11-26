"""Capture phase observations and register an externally applied fault experiment."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from topology import PATHS
from . import PHASES, RECOVERY, _text, _timestamp, register
from .evidence import MODEL_FIELDS, evidence_fields
from .linux import snapshot


def _load(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def _capture(args):
    _text(args.id, "run ID")
    if not args.input and not args.linux:
        raise ValueError("provide --input for operator observations or --linux for local counters")
    record = _load(args.input) if args.input else {}
    if not isinstance(record, dict):
        raise ValueError("the operator input must be a JSON object")
    if record.get("id", args.id) != args.id or record.get("phase", args.phase) != args.phase:
        raise ValueError("input ID or phase differs from the requested capture")
    if args.input:
        _text(record.get("source"), "operator measurement source")
        _timestamp(record.get("observed_at"))
    if args.linux:
        if "linux_counters" in record:
            raise ValueError("input already contains Linux counters for this phase")
        counters = snapshot()
        record["linux_counters"] = counters
        if not args.input:
            record.update(source=counters["host"], observed_at=counters["observed_at"])
    record.update(id=args.id, phase=args.phase)
    if not (record.get("evidence") or record.get("metrics") or record.get("linux_counters")):
        raise ValueError("the phase must contain evidence, measurements or Linux counters")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    catalog = commands.add_parser("evidence", help="show the evidence fields accepted for a fault model")
    catalog.add_argument("model", choices=MODEL_FIELDS)
    capture = commands.add_parser(
        "capture", help="capture one phase from operator JSON or local Linux counters",
        epilog="Use ISO 8601 time with timezone in observed_at. In metrics, each named metric has "
               "samples of [duration_s, value]. The baseline phase also specifies direction "
               "(higher_is_worse or lower_is_worse) and optionally weight, baseline_sigma and scale.")
    capture.add_argument("id")
    capture.add_argument("phase", choices=PHASES)
    capture.add_argument("--linux", action="store_true", help="read this host's CPU, memory and interface counters")
    capture.add_argument("--input", type=Path, help="JSON with source, observed_at, evidence or metrics")
    capture.add_argument("--output", type=Path, help="write phase JSON (default stdout)")
    put = commands.add_parser("register", help="combine three phase files for one run in the results database")
    put.add_argument("database", type=Path)
    put.add_argument("id")
    put.add_argument("files", nargs=3, metavar="PHASE_JSON", type=Path)
    put.add_argument("--model", required=True, choices=MODEL_FIELDS)
    put.add_argument("--path", nargs="+", required=True, help="paper path ID (a-f) or ordered hop names")
    put.add_argument("--target", required=True)
    put.add_argument("--occurrence", type=int, default=1)
    put.add_argument("--parameters", help="JSON object containing the actual applied fault settings")
    put.add_argument("--recovery", required=True, choices=RECOVERY, help="recovery state reported by the operator")
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            data = _capture(args)
        elif args.command == "evidence":
            data = evidence_fields(args.model)
        else:
            path = args.path[0] if len(args.path) == 1 and args.path[0] in PATHS else args.path
            phases = [_load(filename) for filename in args.files]
            parameters = json.loads(args.parameters) if args.parameters else None
            with closing(sqlite3.connect(args.database)) as db:
                key = register(db, args.id, phases, model=args.model, path=path, target=args.target,
                               occurrence=args.occurrence, parameters=parameters, recovery=args.recovery)
            data = {"id": key, "backend": "external-observation"}
        output = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        if args.command == "capture" and args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, sqlite3.Error) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
