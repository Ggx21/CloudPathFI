import argparse
import json
from pathlib import Path

from analysis import analyze, duration_fraction, metric_impact

def main():
    parser = argparse.ArgumentParser(description="Calculate per-hop impact from recorded observations.")
    commands = parser.add_subparsers(dest="command", required=True)
    analysis = commands.add_parser("analyze", help="calculate metric, anomaly and propagation contributions")
    analysis.add_argument("record", type=Path, help="JSON with path and per-hop observations")
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8-sig"))
        result = analyze(record)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
