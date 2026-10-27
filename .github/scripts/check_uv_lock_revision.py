#!/usr/bin/env python3

import os
import subprocess
import tomllib
from pathlib import Path


def exists(rev):
    return (
        subprocess.run(
            ["git", "cat-file", "-e", rev],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


event = os.environ["GITHUB_EVENT_NAME"]

if event == "pull_request":
    base = "HEAD^1"
elif event == "push":
    base = os.getenv("BEFORE_SHA", "")
else:
    print(f"No previous commit for {event}; skipping.")
    raise SystemExit(0)

# Skip if the previous commit does not exist.
if not base or not base.strip("0") or not exists(f"{base}^{{commit}}"):
    print("Previous commit not found; skipping.")
    raise SystemExit(0)

# Skip if uv.lock did not exist in the previous commit.
if not exists(f"{base}:uv.lock"):
    print("Previous uv.lock not found; skipping.")
    raise SystemExit(0)

before = tomllib.loads(
    subprocess.check_output(["git", "show", f"{base}:uv.lock"], text=True)
)
after = tomllib.loads(Path("uv.lock").read_text())

old = (before["version"], before.get("revision", 0))
new = (after["version"], after.get("revision", 0))

if new < old:
    raise SystemExit(f"::error file=uv.lock::Lockfile downgraded: {old} -> {new}")

print(f"Lockfile version OK: {old} -> {new}")
