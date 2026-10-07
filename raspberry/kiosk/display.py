import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from console import console
from kiosk.server import KioskServer

ROOT = Path(__file__).resolve().parent

LABELS = {
    "Recyclable": "RECICLABLE",
    "Organic": "ORGÁNICO",
    "NonRecyclable": "NO RECICLABLE",
}

WAITING = "Coloca tu residuo frente a la cámara"
DETECTED = "¡Residuo detectado! Capturando imagen..."
PROCESSING = "Analizando tu residuo..."
THANKS = "¡Gracias por reciclar!"
ERROR = "No pudimos analizar el residuo. Intenta de nuevo."


@dataclass(frozen=True)
class KioskConfig:
    host: str
    port: int
    open_browser: bool
    detected_seconds: float
    result_seconds: float
    thanks_seconds: float
    error_seconds: float
    bins: dict


def load_kiosk_config() -> KioskConfig:
    raw = json.loads((ROOT / "kiosk.json").read_text(encoding="utf-8"))
    bins = {}
    for color, configured in raw["bins"].items():
        path = Path(configured)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        bins[color] = path
    return KioskConfig(
        host=raw.get("host", "127.0.0.1"),
        port=int(raw.get("port", 8765)),
        open_browser=bool(raw.get("open_browser", True)),
        detected_seconds=float(raw.get("detected_seconds", 1.8)),
        result_seconds=float(raw.get("result_seconds", 6)),
        thanks_seconds=float(raw.get("thanks_seconds", 3.5)),
        error_seconds=float(raw.get("error_seconds", 4)),
        bins=bins,
    )


class KioskApp:
    def __init__(self, config: KioskConfig | None = None):
        self.config = config or load_kiosk_config()
        self._lock = threading.Lock()
        self._timers = []
        self._epoch = 0
        self._session = 0
        self._image_name = None
        self._image_path = None
        self._view = self._waiting_view()
        self._server = None
        self._stopped = threading.Event()
        self._frame_cond = threading.Condition()
        self._jpeg = None
        self._jpeg_seq = 0
        for color, path in self.config.bins.items():
            if not path.is_file():
                console(f"No se encontró la imagen de la caneca {color}: {path}")

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def start(self, open_browser: bool | None = None) -> None:
        self._server = KioskServer(self.config.host, self.config.port, self)
        self._server.start()
        time.sleep(0.2)
        console("", f"Kiosko: {self.url}", "")
        should_open = (
            self.config.open_browser if open_browser is None else open_browser
        )
        if should_open:
            _open_kiosk(self.url)

    def stop(self) -> None:
        self._stopped.set()
        with self._frame_cond:
            self._frame_cond.notify_all()
        with self._lock:
            self._cancel_timers()
        if self._server is not None:
            self._server.stop()
            self._server = None

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def publish_frame(self, jpeg: bytes) -> None:
        with self._frame_cond:
            if self._stopped.is_set():
                return
            self._jpeg = jpeg
            self._jpeg_seq += 1
            self._frame_cond.notify_all()

    def wait_jpeg(self, after: int, timeout: float = 0.5):
        deadline = time.monotonic() + timeout
        with self._frame_cond:
            while not self._stopped.is_set() and (
                self._jpeg is None or self._jpeg_seq <= after
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._frame_cond.wait(remaining)
            if self._stopped.is_set() or self._jpeg is None or self._jpeg_seq <= after:
                return None
            return self._jpeg_seq, self._jpeg

    def show_capture(self, image_path: Path) -> None:
        with self._lock:
            self._cancel_timers()
            self._epoch += 1
            epoch = self._epoch
            self._session += 1
            self._image_name = image_path.name
            self._image_path = image_path
            session = self._session
            self._view = {
                "session": session,
                "state": "detected",
                "title": DETECTED,
                "label": None,
                "color": None,
            }
        self._schedule(
            self.config.detected_seconds,
            epoch,
            lambda: self._apply(
                epoch,
                {
                    "session": session,
                    "state": "processing",
                    "title": PROCESSING,
                    "label": None,
                    "color": None,
                },
            ),
        )

    def show_result(self, image_name: str, payload: dict) -> None:
        classification = payload.get("classification")
        color = payload.get("color")
        label = LABELS.get(classification, classification)
        with self._lock:
            if image_name != self._image_name:
                return
            self._cancel_timers()
            self._epoch += 1
            epoch = self._epoch
            session = self._session
            self._view = {
                "session": session,
                "state": "result",
                "title": label,
                "label": label,
                "color": color,
            }
        self._schedule(
            self.config.result_seconds,
            epoch,
            lambda: self._apply(
                epoch,
                {
                    "session": session,
                    "state": "thanks",
                    "title": THANKS,
                    "label": None,
                    "color": None,
                },
            ),
        )
        self._schedule(
            self.config.result_seconds + self.config.thanks_seconds,
            epoch,
            lambda: self._apply(epoch, self._waiting_view(session)),
        )

    def show_failure(self, image_name: str, error: str) -> None:
        del error
        with self._lock:
            if image_name != self._image_name:
                return
            self._cancel_timers()
            self._epoch += 1
            epoch = self._epoch
            session = self._session
            self._view = {
                "session": session,
                "state": "error",
                "title": ERROR,
                "label": None,
                "color": None,
            }
        self._schedule(
            self.config.error_seconds,
            epoch,
            lambda: self._apply(epoch, self._waiting_view(session)),
        )

    def snapshot(self) -> dict:
        with self._lock:
            view = dict(self._view)
            has_photo = self._image_path is not None and view["state"] in {
                "processing",
                "result",
            }
            color = view.get("color")
        view["photo"] = has_photo
        view["bin"] = bool(color and color in self.config.bins)
        return view

    def photo_path(self) -> Path | None:
        with self._lock:
            if self._view["state"] not in {"processing", "result"}:
                return None
            return self._image_path

    def bin_path(self, color: str) -> Path | None:
        path = self.config.bins.get(color)
        if path is not None and path.is_file():
            return path
        return None

    def _waiting_view(self, session: int | None = None) -> dict:
        return {
            "session": self._session if session is None else session,
            "state": "waiting",
            "title": WAITING,
            "label": None,
            "color": None,
        }

    def _apply(self, epoch: int, view: dict) -> None:
        with self._lock:
            if epoch != self._epoch:
                return
            self._view = view
            if view["state"] == "waiting":
                self._image_name = None
                self._image_path = None

    def _schedule(self, delay: float, epoch: int, action) -> None:
        def run() -> None:
            with self._lock:
                if epoch != self._epoch:
                    return
            action()

        timer = threading.Timer(delay, run)
        timer.daemon = True
        with self._lock:
            self._timers.append(timer)
        timer.start()

    def _cancel_timers(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers = []


def _open_kiosk(url: str) -> None:
    browser = _find_kiosk_browser()
    if browser is not None:
        try:
            subprocess.Popen(
                [browser, "--kiosk", "--no-first-run", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    webbrowser.open(url)


def _find_kiosk_browser() -> str | None:
    if sys.platform == "win32":
        roots = [
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        relative = (
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Microsoft/Edge/Application/msedge.exe"),
        )
        for root in roots:
            if not root:
                continue
            for name in relative:
                candidate = Path(root) / name
                if candidate.is_file():
                    return str(candidate)
        return None
    for name in (
        "chromium-browser",
        "chromium",
        "google-chrome",
        "google-chrome-stable",
    ):
        found = shutil.which(name)
        if found:
            return found
    return None
