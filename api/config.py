"""Vercel function: /api/config  (logic lives in _google.py)."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _google import handle  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, body = handle(self.path)
        out = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)
