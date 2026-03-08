#!/usr/bin/env python3
"""Push agent state to the local OpenClaw board."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

DEFAULT_TASK_TITLE = 'Idle'
VALID_STATES = {'idle', 'writing', 'researching', 'executing', 'syncing', 'error'}
STATE_ALIASES = {
    'idle': 'idle',
    'writing': 'writing',
    'researching': 'researching',
    'executing': 'executing',
    'syncing': 'syncing',
    'error': 'error',
    'receiving': 'researching',
    'replying': 'writing',
}


def normalize_state(value, fallback: str = 'executing') -> str:
    raw = str(value or '').strip().lower()
    if raw in STATE_ALIASES:
        return STATE_ALIASES[raw]
    if raw in VALID_STATES:
        return raw
    return fallback


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Push agent state to OpenClaw Agent Monitor')
    parser.add_argument('state', help='State, such as idle / executing / researching')
    parser.add_argument('detail', nargs='?', default=DEFAULT_TASK_TITLE, help='Current task detail')
    parser.add_argument('--agent-id', default=os.environ.get('OPENCLAW_AGENT_ID', 'coding'))
    parser.add_argument('--session-key', default=os.environ.get('OPENCLAW_SESSION_KEY', ''))
    parser.add_argument(
        '--url',
        default=os.environ.get('OPENCLAW_AGENT_BOARD_PUSH_URL', 'http://127.0.0.1:7654/api/push'),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = {
        'agentId': args.agent_id,
        'state': normalize_state(args.state),
        'taskTitle': args.detail,
        'sessionKey': args.session_key,
        'updatedAt': int(time.time() * 1000),
    }

    request = urllib.request.Request(
        args.url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            sys.stdout.write(response.read().decode('utf-8'))
            sys.stdout.write('\n')
    except Exception as exc:
        print(f'push failed: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
