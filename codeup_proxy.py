import http.server
import urllib.request
import urllib.error
import json
import sys
import traceback

TARGET_HOST = 'https://codeup.aliyun.com'

def read_exact(rfile, n):
    data = bytearray()
    while len(data) < n:
        packet = rfile.read(n - len(data))
        if not packet:
            raise IOError(f"Unexpected EOF reading {n} bytes (read {len(data)})")
        data.extend(packet)
    return bytes(data)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self):
        self.handle_proxy('GET')

    def do_POST(self):
        self.handle_proxy('POST')

    def do_PUT(self):
        self.handle_proxy('PUT')

    def do_DELETE(self):
        self.handle_proxy('DELETE')

    def read_request_body(self):
        te = self.headers.get('Transfer-Encoding', '').lower()
        if 'chunked' in te:
            chunks = []
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                chunk_header = line.split(b';')[0].strip()
                if not chunk_header:
                    continue
                try:
                    chunk_size = int(chunk_header, 16)
                except ValueError:
                    sys.stderr.write(f"[Proxy] Invalid chunk size header: {chunk_header!r}\n")
                    break
                if chunk_size == 0:
                    while True:
                        trailer = self.rfile.readline()
                        if not trailer or trailer.strip() == b'':
                            break
                    break
                chunk_data = read_exact(self.rfile, chunk_size)
                chunks.append(chunk_data)
                self.rfile.readline()  # trailing \r\n
            body = b''.join(chunks)
            sys.stderr.write(f"[Proxy] De-chunked request body ({len(body)} bytes) for {self.path}\n")
            return body
        else:
            content_length = int(self.headers.get('Content-Length', 0))
            return self.rfile.read(content_length) if content_length > 0 else None

    def handle_proxy(self, method):
        try:
            body = self.read_request_body()

            if self.path.endswith('/info/lfs/objects/batch') and body:
                try:
                    data = json.loads(body.decode('utf-8'))
                    if not data.get('ref'):
                        data['ref'] = {'name': 'HEAD'}
                        body = json.dumps(data).encode('utf-8')
                        sys.stderr.write(f"[Proxy] Injected ref into LFS batch for {self.path}\n")
                except Exception as e:
                    sys.stderr.write(f"[Proxy] JSON parse error: {e}\n")

            target_url = TARGET_HOST + self.path
            req = urllib.request.Request(target_url, data=body, method=method)

            for k, v in self.headers.items():
                if k.lower() not in ['host', 'content-length', 'transfer-encoding', 'connection']:
                    req.add_header(k, v)
            if body is not None:
                req.add_header('Content-Length', str(len(body)))
            elif method in ['POST', 'PUT']:
                req.add_header('Content-Length', '0')

            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in ['transfer-encoding', 'connection', 'content-length']:
                            self.send_header(k, v)
                    self.send_header('Content-Length', str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
            except urllib.error.HTTPError as e:
                resp_body = e.read()
                sys.stderr.write(f"[Proxy] HTTPError {e.code} for {self.path} (body len {len(resp_body)})\n")
                self.send_response(e.code)
                for k, v in e.headers.items():
                    if k.lower() not in ['transfer-encoding', 'connection', 'content-length']:
                        self.send_header(k, v)
                self.send_header('Content-Length', str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except Exception as e:
            sys.stderr.write(f"[Proxy] Proxy exception for {self.path}: {e}\n")
            traceback.print_exc()
            err_msg = str(e).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

if __name__ == '__main__':
    port = 8899
    server = http.server.ThreadingHTTPServer(('0.0.0.0', port), ProxyHandler)
    sys.stderr.write(f"Codeup Proxy listening on port {port}...\n")
    server.serve_forever()
