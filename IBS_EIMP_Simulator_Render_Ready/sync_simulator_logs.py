#!/usr/bin/env python3
"""Synchronize synthetic IBS/EIMP simulator logs to local Unix training folders.

Uses only Python standard library. The session ID is a bearer capability:
do not share it or put it in public source control.
"""
import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

LOGS = ["access.log", "error.log", "application.log", "catalina.out",
        "database.log", "batch.log", "gc.log", "thread_dump.log", "startup.log"]
REQUEST = re.compile(r"(IBS|EIMP)-REQ-[A-F0-9]{8}")
PATHS = {
    "access.log": ("webserver/var/log/httpd/ibs_access_log", "webserver/var/log/httpd/eimp_access_log"),
    "error.log": ("webserver/var/log/httpd/ibs_error_log", "webserver/var/log/httpd/eimp_error_log"),
}
def destination(root, project, logname):
    if logname in PATHS:
        relative = PATHS[logname][0 if project == "IBS" else 1]
    else:
        relative = "appserver/opt/tomcat/logs/" + logname
    return root / (project + "_Server_Lab") / relative

def sync(base_url, session, root, offsets):
    for name in LOGS:
        url = base_url.rstrip("/") + "/api/logs/" + name
        req = urllib.request.Request(url, headers={"X-Lab-Session": session})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)
        lines = data["lines"]
        previous = offsets.get(name, 0)
        if previous > len(lines):
            previous = 0  # Simulator reset or restarted.
        # Only copy new entries. The remote simulator keeps at most 1200 lines
        # per log, so poll frequently to avoid losing lines.
        grouped = {"IBS": [], "EIMP": []}
        for line in lines[previous:]:
            match = REQUEST.search(line)
            if match:
                grouped[match.group(1)].append(line)
        for project, entries in grouped.items():
            if not entries:
                continue
            path = destination(root, project, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(entries) + "\n")
            print(f"{project}: appended {len(entries)} lines to {path}", flush=True)
        offsets[name] = len(lines)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="X-Lab-Session from your browser")
    parser.add_argument("--root", default=str(Path.home()), help="Parent of IBS_Server_Lab and EIMP_Server_Lab")
    parser.add_argument("--url", default="https://ibs-eimp-sim.onrender.com")
    parser.add_argument("--interval", type=int, default=30, help="Polling seconds (default: 30)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.session):
        parser.error("Invalid session identifier")
    root = Path(args.root).expanduser().resolve()
    if not (root / "IBS_Server_Lab").is_dir() or not (root / "EIMP_Server_Lab").is_dir():
        parser.error("Both IBS_Server_Lab and EIMP_Server_Lab must already exist under --root")
    offsets = {}
    print("Synchronizing synthetic training logs. Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            try:
                sync(args.url, args.session, root, offsets)
            except Exception as exc:
                print(f"Sync error (will retry): {exc}", flush=True)
            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
