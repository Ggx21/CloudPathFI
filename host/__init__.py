"""Run a bounded UDP echo experiment inside a fresh Linux network namespace."""

import json
import os
from pathlib import Path
import subprocess
import sys

from .probe import system_tool, validate_job


def run_job(job):
    """Return a measured experiment record; raise ValueError or RuntimeError on failure."""
    job = validate_job(job)
    if not sys.platform.startswith("linux"):
        raise RuntimeError("the UDP measurement backend requires Linux network namespaces")
    command = [system_tool("unshare")]
    if os.geteuid() != 0:
        command.extend(["--user", "--map-root-user"])
    worker = Path(__file__).with_name("probe.py").resolve()
    command.extend(["--net", "--", sys.executable, "-I", "-B", str(worker)])
    try:
        # Capture the original namespace identity before creating the child user
        # namespace, which can restrict access to /proc entries for the parent.
        namespace_fd = os.open("/proc/self/ns/net", os.O_RDONLY)
        try:
            result = subprocess.run([*command, str(namespace_fd)], pass_fds=(namespace_fd,),
                                    input=json.dumps(job), capture_output=True, text=True,
                                    encoding="utf-8", timeout=30, check=False,
                                    env={"PATH": os.defpath, "LC_ALL": "C"})
        finally:
            os.close(namespace_fd)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"could not complete the isolated UDP experiment: {error}") from error
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"namespace worker exited with status {result.returncode}")
    return json.loads(result.stdout)
