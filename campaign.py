"""Run a packet-loss or delay experiment on a virtual clock."""

from experiment import simulate, summarize
from experiment.cli import main

__all__ = ["simulate", "summarize", "main"]


if __name__ == "__main__":
    main()
