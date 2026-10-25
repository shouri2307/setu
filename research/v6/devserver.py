"""Tiny static server for the web/ folder with caching disabled (so edits show up on reload).  python research/v6/devserver.py 8123"""
import http.server, socketserver, sys, os
os.chdir(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0"); super().end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer.allow_reuse_address = True
with http.server.ThreadingHTTPServer(("", int(sys.argv[1]) if len(sys.argv) > 1 else 8123), H) as s: s.serve_forever()
