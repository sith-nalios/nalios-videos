from http.server import HTTPServer, BaseHTTPRequestHandler
import json, datetime

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        print(f"\n{'='*60}")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] XML reçu sur {self.path}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n", flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
    def log_message(self, *args): pass

HTTPServer(('localhost', 9999), Handler).serve_forever()
