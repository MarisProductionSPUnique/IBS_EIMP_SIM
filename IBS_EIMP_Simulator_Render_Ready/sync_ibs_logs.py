#!/usr/bin/env python3
"""Append simulated online IBS incident logs into existing IBS_Server_Lab log paths.

Use the session ID displayed at /ibs-training; no credentials or real Oracle access needed.
Run manually or with --watch; never replaces existing log files.
"""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

MAPPING = {
    'access.log': 'webserver/var/log/httpd/ibs_access_log',
    'error.log': 'webserver/var/log/httpd/ibs_error_log',
    'application.log': 'appserver/opt/tomcat/logs/application.log',
    'catalina.out': 'appserver/opt/tomcat/logs/catalina.out',
    'database.log': 'database/logs/oracle_alert.log',
    'batch.log': 'appserver/opt/tomcat/logs/batch.log',
    'gc.log': 'appserver/opt/tomcat/logs/gc.log',
    'thread_dump.log': 'appserver/opt/tomcat/logs/thread_dump.log',
    'startup.log': 'appserver/opt/tomcat/logs/startup.log',
}

def sync(base, session, host, state_path):
    cursor = {}
    if state_path.is_file():
        try:
            cursor = json.loads(state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            print('Warning: Cannot load prior cursor; review current files to avoid duplicates.')
            return
    # Each online session is separate. Never reuse a cursor from another session.
    if cursor.get('session_id') != session:
        cursor = {'session_id': session, 'counts': {}}
    counts = cursor['counts']
    additions = 0
    for logname, relative in MAPPING.items():
        url = host.rstrip('/') + '/api/logs/' + logname
        req = Request(url, headers={'X-Lab-Session': session, 'Accept': 'application/json'}, method='GET')
        try:
            with urlopen(req, timeout=20) as reply:
                data = json.load(reply)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            print(f'Failed retrieving {logname}: {exc}')
            continue
        lines = data.get('lines') or []
        n = len(lines)
        previous = int(counts.get(logname, 0))
        if n < previous:
            # Render may have restarted/reset its in-memory logs.
            print(f'{logname}: source session reset/rotated; re-syncing current data.')
            previous = 0
        new = lines[previous:]
        if new:
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('a', encoding='utf-8') as stream:
                stream.write('\n'.join(new)+'\n')
            print(f'{logname}: appended {len(new)} lines -> {target}')
            additions += len(new)
        counts[logname] = n
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(cursor, indent=2), encoding='utf-8')
    tmp.replace(state_path)
    print(f'Sync finished: {additions} new synthetic log lines. Original log contents retained.')


def main():
    parser = argparse.ArgumentParser(description='Sync synthetic IBS logs to existing IBS_Server_Lab layout')
    parser.add_argument('--session', required=True, help='Browser session ID shown in IBS training page')
    parser.add_argument('--lab', default=str(Path.home()/'IBS_Server_Lab'), help='Existing IBS_Server_Lab path')
    parser.add_argument('--host', default='https://ibs-eimp-sim.onrender.com')
    parser.add_argument('--watch', type=int, default=0, metavar='SECONDS', help='Repeat every N seconds (at least 5)')
    args = parser.parse_args()
    base = Path(args.lab).expanduser().resolve()
    if not base.is_dir():
        parser.error(f'Lab directory does not exist: {base}. Extract your IBS_EIMP_lab.zip first.')
    if not (base/'appserver/opt/tomcat/logs').is_dir() or not (base/'webserver/var/log/httpd').is_dir():
        parser.error('Incorrect IBS_Server_Lab layout (missing Tomcat or Apache log paths).')
    if not args.host.startswith('https://'):
        parser.error('--host must use HTTPS')
    if args.watch and args.watch < 5:
        parser.error('--watch must be at least 5 seconds')
    state_path = base/'training/.ibs_online_log_sync.json'
    while True:
        sync(base, args.session, args.host, state_path)
        if not args.watch:
            break
        time.sleep(args.watch)

if __name__=='__main__':
    main()
