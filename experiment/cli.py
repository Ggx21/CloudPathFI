"""Run a packet-loss or delay experiment on a virtual clock."""

import argparse
import json
from pathlib import Path

from topology import PATHS, read_path
from .simulation import simulate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("FM-07", "FM-08"))
    paths = parser.add_mutually_exclusive_group(required=True)
    paths.add_argument("--path", nargs="+", metavar="HOP", help="a paper path ID (a-f) or ordered hop names")
    paths.add_argument("--path-file", type=Path, help="JSON containing a path ID, list, or object with a path field")
    parser.add_argument("--hop", required=True, help="apply the fault at this hop on arrival")
    parser.add_argument("--occurrence", type=int, default=1, help="visit to the selected hop, starting at 1")
    parser.add_argument("--id", "--experiment-id", dest="experiment_id", help="experiment ID (default: derived from settings and path)")
    parser.add_argument("--start-ms", type=int, default=20, help="inclusive window start")
    parser.add_argument("--end-ms", type=int, default=60, help="exclusive window end")
    parser.add_argument("--packets", type=int, default=10)
    parser.add_argument("--interval-ms", type=int, default=10, help="time between sends")
    parser.add_argument("--hop-ms", type=int, default=1, help="base transit time per hop")
    parser.add_argument("--loss-pct", type=float, help="FM-07 loss probability in percent (default 25)")
    parser.add_argument("--delay-ms", type=int, help="FM-08 extra time at the hop (default 50)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, help="write JSON to this file (default stdout)")
    options = vars(parser.parse_args(argv))
    output = options.pop("output")
    path_file = options.pop("path_file")
    try:
        path = options["path"]
        if path_file is not None:
            options["path"] = read_path(path_file)
        elif len(path) == 1 and path[0] in PATHS:
            options["path"] = path[0]
        report = json.dumps(simulate(**options), indent=2, allow_nan=False)
        if output:
            output.write_text(report + "\n", encoding="utf-8")
        else:
            print(report)
    except (OSError, ValueError, OverflowError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
