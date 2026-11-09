"""Loopback-only JSON control panel, usable with ROS or the portable preview."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

def serve(web_directory, snapshot, submit, port=8765):
    page = (Path(web_directory)/'index.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, body, content_type='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/':
                self.respond(200, page, 'text/html; charset=utf-8')
            elif self.path == '/api/state':
                self.respond(200, snapshot())
            else:
                self.respond(404, {'error': 'not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                self.respond(403, {'error': 'origin rejected'})
                return
            if self.path != '/api/action':
                self.respond(404, {'error': 'not found'})
                return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 4096 or not self.headers.get('Content-Type', '').startswith('application/json'):
                    raise ValueError('JSON body required (max 4096 bytes)')
                message = json.loads(self.rfile.read(size))
                if not isinstance(message, dict):
                    raise ValueError('object required')
                answer = submit(message)
                self.respond(202, answer or {'queued': True})
            except (ValueError, KeyError, TypeError) as error:
                self.respond(400, {'error': str(error)})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
