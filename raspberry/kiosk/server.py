import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WEB = Path(__file__).resolve().parent / "web"


class KioskServer:
    def __init__(self, host: str, port: int, app):
        self.host = host
        self.port = port
        handler = kiosk_handler(app)
        ThreadingHTTPServer.allow_reuse_address = True
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="kiosk-http",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def kiosk_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            route = parsed.path
            if route == "/":
                self._send_file(WEB / "index.html")
            elif route == "/kiosk.css":
                self._send_file(WEB / "kiosk.css")
            elif route == "/kiosk.js":
                self._send_file(WEB / "kiosk.js")
            elif route == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif route == "/api/state":
                body = json.dumps(app.snapshot(), ensure_ascii=False).encode("utf-8")
                self._send_bytes(body, "application/json; charset=utf-8")
            elif route == "/media/live":
                self._stream_live()
            elif route == "/media/photo":
                photo = app.photo_path()
                if photo is None:
                    self.send_error(404)
                    return
                self._send_file(photo)
            elif route == "/media/bin":
                color = parse_qs(parsed.query).get("color", [""])[0]
                image = app.bin_path(color)
                if image is None:
                    self.send_error(404)
                    return
                self._send_file(image)
            else:
                self.send_error(404)

        def log_message(self, fmt: str, *args) -> None:
            return

        def _stream_live(self) -> None:
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame",
            )
            self.end_headers()
            sequence = 0
            try:
                while True:
                    item = app.wait_jpeg(sequence, 0.5)
                    if item is None:
                        if app.stopped:
                            break
                        continue
                    sequence, jpeg = item
                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: "
                        + str(len(jpeg)).encode("ascii")
                        + b"\r\n\r\n"
                    )
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
            except (ConnectionError, OSError):
                return

        def _send_file(self, path) -> None:
            if not path.is_file():
                self.send_error(404)
                return
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".svg":
                mime = "image/svg+xml"
            self._send_bytes(path.read_bytes(), mime)

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler
