#!/usr/bin/env python3
"""Static server with HTTP Range support.

Python's http.server answers Range with a full 200, so browsers cannot
seek inside sample.mp4 and playback snaps back to the start.
"""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))


class RangeHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_HEAD(self):
        path = self.translate_path(self.path.split("?", 1)[0])
        if self.headers.get("Range") and os.path.isfile(path):
            self.send_range(path, self.headers.get("Range"), send_body=False)
            return
        super().do_HEAD()

    def do_GET(self):
        path = self.translate_path(self.path.split("?", 1)[0])
        range_header = self.headers.get("Range")
        if range_header and os.path.isfile(path):
            self.send_range(path, range_header)
            return
        super().do_GET()

    def send_range(self, path, range_header, send_body=True):
        size = os.path.getsize(path)
        try:
            units, spec = range_header.split("=", 1)
            if units.strip() != "bytes":
                raise ValueError
            start_s, end_s = spec.split("-", 1)
            if start_s == "":
                length = int(end_s)
                start = max(0, size - length)
                end = size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1
        except ValueError:
            self.send_error(416, "Invalid range")
            return
        if start < 0 or start >= size or end < start:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        end = min(end, size - 1)
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if not send_body:
            return
        with open(path, "rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)


if __name__ == "__main__":
    os.chdir(ROOT)
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), RangeHandler)
    print(f"Serving {ROOT} at http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
