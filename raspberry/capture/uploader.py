import queue
import threading
import time

import requests

from capture.store import CaptureStore
from config.settings import Settings
from console import console

CLASSIFICATION_LABELS = {
    "Recyclable": "RECICLABLE",
    "Organic": "ORGANICO",
    "NonRecyclable": "NO RECICLABLE",
}


class BackendUploader:
    def __init__(self, settings: Settings, store: CaptureStore):
        self.settings = settings
        self.store = store
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._queued = set()
        self._lock = threading.Lock()
        self.on_success = None
        self.on_failure = None
        self._thread = threading.Thread(
            target=self._run,
            name="backend-uploader",
            daemon=True,
        )

    def start(self) -> None:
        for metadata in self.store.pending():
            self.submit(metadata["image"], announce=False)
        self._thread.start()

    def submit(self, image_name: str, announce: bool = True) -> None:
        with self._lock:
            if image_name in self._queued:
                return
            self._queued.add(image_name)
        if announce:
            console("Enviando imagen al backend...")
        self._queue.put((image_name, announce))

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                image_name, announce = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._send(image_name, announce)
            finally:
                with self._lock:
                    self._queued.discard(image_name)
                self._queue.task_done()

    def _send(self, image_name: str, announce: bool) -> None:
        metadata = self.store.load(image_name)
        image_path = self.store.image_path(image_name)
        url = f"{self.settings.backend_url}/classify"
        last_error = "backend no disponible"

        for attempt in range(1, self.settings.max_retries + 1):
            if self._stop.is_set():
                return
            if attempt > 1:
                console(
                    f"Reintento {attempt}/{self.settings.max_retries} "
                    f"de {image_name}"
                )
            try:
                with image_path.open("rb") as image_file:
                    response = requests.post(
                        url,
                        files={"file": (image_name, image_file, "image/jpeg")},
                        timeout=self.settings.request_timeout_seconds,
                    )
                payload = response.json()
                if response.status_code >= 400 or not payload.get("success"):
                    raise RuntimeError(
                        payload.get("error") or f"HTTP {response.status_code}"
                    )
                metadata["sent_to_backend"] = True
                metadata["classification"] = payload.get("classification")
                metadata["attempts"] = attempt
                metadata["last_error"] = None
                self.store.update(metadata)
                label = CLASSIFICATION_LABELS.get(
                    metadata["classification"],
                    metadata["classification"],
                )
                console(
                    "",
                    "Backend respondió correctamente",
                    "",
                    "Clasificación:",
                    str(label),
                )
                if announce:
                    self._notify(self.on_success, image_name, payload)
                return
            except Exception as exc:
                last_error = str(exc)
                metadata["sent_to_backend"] = False
                metadata["attempts"] = attempt
                metadata["last_error"] = last_error
                self.store.update(metadata)
                if attempt < self.settings.max_retries:
                    time.sleep(self.settings.retry_backoff_seconds)

        console(
            "",
            "Backend no disponible. La imagen queda guardada para reintentar.",
            self.store.relative_image(image_name),
            last_error,
        )
        if announce:
            self._notify(self.on_failure, image_name, last_error)

    def _notify(self, callback, image_name: str, payload) -> None:
        if callback is None:
            return
        try:
            callback(image_name, payload)
        except Exception as exc:
            console(f"Kiosko: {exc}")
