#!/usr/bin/env python3
"""OpenClaw Agent Monitor server."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / 'agent-state.json'
HISTORY_FILE = BASE_DIR / 'agent-history.json'
LEGACY_HISTORY_FILE = BASE_DIR / 'agent-history.jsonl'
INDEX_FILE = BASE_DIR / 'index.html'
ASSETS_DIR = BASE_DIR / 'assets'

HOST = os.environ.get('OPENCLAW_AGENT_BOARD_HOST', '0.0.0.0')
HTTP_PORT = int(os.environ.get('OPENCLAW_AGENT_BOARD_PORT', '7654'))
WS_PORT = int(os.environ.get('OPENCLAW_AGENT_BOARD_WS_PORT', '7655'))

VALID_STATES = {'idle', 'writing', 'researching', 'executing', 'syncing', 'error'}
DEFAULT_TASK_TITLE = 'Idle'
MAX_HISTORY_ITEMS = 100
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
WS_MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

ws_clients: list[socket.socket] = []
ws_lock = threading.Lock()
state_lock = threading.Lock()
history_lock = threading.Lock()
last_payload = ''


def now_ms() -> int:
    return int(time.time() * 1000)


def clean_text(value, default: str = '') -> str:
    text = str(default if value is None else value).strip()
    return ' '.join(text.split()) or default


def normalize_state(value, fallback: str = 'idle') -> str:
    raw = clean_text(value).lower()
    if raw in STATE_ALIASES:
        return STATE_ALIASES[raw]
    if raw in VALID_STATES:
        return raw
    return fallback


def clamp_history_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return MAX_HISTORY_ITEMS
    return max(1, min(MAX_HISTORY_ITEMS, limit))


def format_timestamp(timestamp_ms: int) -> str:
    base_seconds = (int(timestamp_ms) / 1000) if timestamp_ms else time.time()
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(base_seconds))


def read_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = STATE_FILE.with_suffix('.tmp')
    temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp_file.replace(STATE_FILE)


def write_history_store(data: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = HISTORY_FILE.with_suffix('.tmp')
    temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp_file.replace(HISTORY_FILE)


def read_history_store() -> dict:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    if not LEGACY_HISTORY_FILE.exists():
        return {}

    migrated: dict[str, list[dict]] = {}
    try:
        with LEGACY_HISTORY_FILE.open('r', encoding='utf-8') as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue

                agent_id = clean_text(entry.get('agentId'))
                if not agent_id:
                    continue

                item = {
                    'state': normalize_state(entry.get('state'), fallback='idle'),
                    'taskTitle': clean_text(entry.get('taskTitle'), DEFAULT_TASK_TITLE),
                    'sessionKey': clean_text(entry.get('sessionKey'), ''),
                    'updatedAt': int(entry.get('updatedAt') or 0),
                }
                migrated.setdefault(agent_id, []).append(item)
    except Exception:
        return {}

    normalized: dict[str, list[dict]] = {}
    for agent_id, items in migrated.items():
        normalized[agent_id] = items[-MAX_HISTORY_ITEMS:]

    if normalized:
        try:
            write_history_store(normalized)
        except Exception:
            pass
    return normalized


def append_history(agent_id: str, item: dict) -> None:
    entry = {
        'state': item['state'],
        'taskTitle': item['taskTitle'],
        'sessionKey': item['sessionKey'],
        'updatedAt': int(item['updatedAt'] or now_ms()),
    }
    with history_lock:
        data = read_history_store()
        agent_items = data.get(agent_id)
        if not isinstance(agent_items, list):
            agent_items = []
        agent_items.append(entry)
        data[agent_id] = agent_items[-MAX_HISTORY_ITEMS:]
        write_history_store(data)


def build_history(agent_id: str, limit: int = MAX_HISTORY_ITEMS) -> list[dict]:
    agent_key = clean_text(agent_id)
    if not agent_key:
        return []

    with history_lock:
        data = read_history_store()

    raw_items = data.get(agent_key)
    if not isinstance(raw_items, list):
        return []

    items: deque[dict] = deque(maxlen=clamp_history_limit(limit))
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue

        updated_at = int(entry.get('updatedAt') or 0)
        task_title = clean_text(entry.get('taskTitle'), DEFAULT_TASK_TITLE)
        items.append(
            {
                'updatedAt': updated_at,
                'state': normalize_state(entry.get('state'), fallback='idle'),
                'taskTitle': task_title,
                'text': f'{format_timestamp(updated_at)} : {task_title}',
            }
        )

    return list(reversed(items))


def build_agents() -> list[dict]:
    with state_lock:
        data = read_state()

    agents: list[dict] = []
    for agent_id, item in data.items():
        if not isinstance(item, dict):
            continue

        agents.append(
            {
                'agentId': clean_text(agent_id),
                'state': normalize_state(item.get('state'), fallback='idle'),
                'taskTitle': clean_text(item.get('taskTitle'), DEFAULT_TASK_TITLE),
                'sessionKey': clean_text(item.get('sessionKey'), ''),
                'updatedAt': int(item.get('updatedAt') or 0),
                'source': 'push',
            }
        )

    agents.sort(key=lambda item: (item['state'] == 'idle', -(item['updatedAt'] or 0), item['agentId']))
    return agents


def build_payload() -> dict:
    agents = build_agents()
    return {
        'ok': True,
        'updatedAt': max((agent['updatedAt'] for agent in agents), default=0),
        'agents': agents,
    }


def payload_text() -> str:
    return json.dumps(build_payload(), ensure_ascii=False)


def save_update(body: dict) -> dict:
    if not isinstance(body, dict):
        raise ValueError('invalid json')

    agent_id = clean_text(body.get('agentId'))
    if not agent_id:
        raise ValueError('agentId required')

    item = {
        'state': normalize_state(body.get('state'), fallback='idle'),
        'taskTitle': clean_text(body.get('taskTitle'), DEFAULT_TASK_TITLE),
        'sessionKey': clean_text(body.get('sessionKey'), ''),
        'updatedAt': int(body.get('updatedAt') or now_ms()),
    }

    with state_lock:
        data = read_state()
        data[agent_id] = item
        write_state(data)

    append_history(agent_id, item)
    return {'agentId': agent_id, **item}


def render_index() -> str:
    return INDEX_FILE.read_text(encoding='utf-8').replace('__WS_PORT__', str(WS_PORT))


def resolve_asset_path(request_path: str) -> Path | None:
    if not request_path.startswith('/assets/'):
        return None

    relative_path = unquote(request_path.lstrip('/'))
    asset_path = (BASE_DIR / relative_path).resolve()
    try:
        asset_path.relative_to(ASSETS_DIR.resolve())
    except ValueError:
        return None
    if not asset_path.is_file():
        return None
    return asset_path


def build_ws_frame(text: str) -> bytes:
    payload = text.encode('utf-8')
    frame = bytearray([0x81])
    payload_size = len(payload)

    if payload_size < 126:
        frame.append(payload_size)
    elif payload_size < 65536:
        frame.append(126)
        frame.extend(payload_size.to_bytes(2, 'big'))
    else:
        frame.append(127)
        frame.extend(payload_size.to_bytes(8, 'big'))

    frame.extend(payload)
    return bytes(frame)


def broadcast(force: bool = False) -> None:
    global last_payload

    text = payload_text()
    if not force and text == last_payload:
        return

    frame = build_ws_frame(text)
    with ws_lock:
        alive_clients: list[socket.socket] = []
        for client in ws_clients:
            try:
                client.sendall(frame)
                alive_clients.append(client)
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

        ws_clients[:] = alive_clients
        last_payload = text


def websocket_watch_loop() -> None:
    while True:
        try:
            broadcast(force=False)
        except Exception:
            pass
        time.sleep(0.2)


def extract_websocket_key(handshake: str) -> str:
    for line in handshake.split('\r\n'):
        if line.lower().startswith('sec-websocket-key:'):
            return line.split(':', 1)[1].strip()
    return ''


def websocket_client_loop(conn: socket.socket) -> None:
    try:
        handshake = conn.recv(4096).decode('utf-8', errors='ignore')
        websocket_key = extract_websocket_key(handshake)
        if not websocket_key:
            conn.close()
            return

        accept_value = base64.b64encode(
            hashlib.sha1((websocket_key + WS_MAGIC).encode('utf-8')).digest()
        ).decode('utf-8')
        conn.sendall(
            (
                'HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept_value}\r\n\r\n'
            ).encode('utf-8')
        )

        with ws_lock:
            ws_clients.append(conn)

        conn.sendall(build_ws_frame(payload_text()))

        while conn.recv(1024):
            pass
    except Exception:
        pass
    finally:
        with ws_lock:
            if conn in ws_clients:
                ws_clients.remove(conn)
        try:
            conn.close()
        except Exception:
            pass


def websocket_server_loop() -> None:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, WS_PORT))
    server_socket.listen(20)

    while True:
        conn, _ = server_socket.accept()
        threading.Thread(target=websocket_client_loop, args=(conn,), daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def send_body(self, code: int, body, content_type: str = 'application/json; charset=utf-8') -> None:
        payload = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, file_path: Path) -> None:
        payload = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', '0') or '0')
        raw_body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            return json.loads(raw_body.decode('utf-8'))
        except Exception:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/agents':
            return self.send_body(200, payload_text())
        if path == '/api/history':
            query = parse_qs(parsed.query)
            agent_id = clean_text((query.get('agentId') or [''])[0])
            if not agent_id:
                return self.send_body(400, json.dumps({'ok': False, 'error': 'agentId required'}, ensure_ascii=False))

            limit = clamp_history_limit((query.get('limit') or [MAX_HISTORY_ITEMS])[0])
            items = build_history(agent_id, limit)
            return self.send_body(200, json.dumps({'ok': True, 'agentId': agent_id, 'items': items}, ensure_ascii=False))
        if path in ('/', '/index.html'):
            return self.send_body(200, render_index(), 'text/html; charset=utf-8')

        asset_path = resolve_asset_path(path)
        if asset_path:
            return self.send_file(asset_path)
        return self.send_body(404, 'Not Found', 'text/plain; charset=utf-8')

    def do_POST(self):
        if urlparse(self.path).path != '/api/push':
            return self.send_body(404, 'Not Found', 'text/plain; charset=utf-8')

        try:
            saved = save_update(self.read_json_body())
        except ValueError as exc:
            return self.send_body(400, json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))

        broadcast(force=True)
        return self.send_body(200, json.dumps({'ok': True, 'saved': saved}, ensure_ascii=False))

    def log_message(self, *_):
        return


def run() -> None:
    threading.Thread(target=websocket_server_loop, daemon=True).start()
    threading.Thread(target=websocket_watch_loop, daemon=True).start()
    ThreadingHTTPServer((HOST, HTTP_PORT), Handler).serve_forever()


if __name__ == '__main__':
    run()


