"""Loopback-only media review server with HTTP Range support for video seeking."""

import argparse
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        self.byte_range = None
        path = Path(self.translate_path(self.path))
        header = self.headers.get("Range")
        if header and path.is_file():
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
            if not match:
                self.send_error(416)
                return None
            size = path.stat().st_size
            start = int(match[1])
            end = min(int(match[2]) if match[2] else size - 1, size - 1)
            if start > end:
                self.send_error(416)
                return None
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            f = path.open("rb")
            f.seek(start)
            self.byte_range = (start, end)
            return f
        return super().send_head()

    def copyfile(self, source, outputfile):
        if not self.byte_range:
            return super().copyfile(source, outputfile)
        left = self.byte_range[1] - self.byte_range[0] + 1
        while left:
            part = source.read(min(left, 65536))
            if not part:
                break
            outputfile.write(part)
            left -= len(part)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=7332)
    a = p.parse_args()
    print(f"http://127.0.0.1:{a.port}/preview.html", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
