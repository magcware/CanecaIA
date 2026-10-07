import json
import re
import threading
from datetime import datetime
from pathlib import Path

import cv2


class CaptureStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = self._last_sequence()

    def save(self, frame, confidence: float, bbox: tuple[int, int, int, int]) -> dict:
        with self._lock:
            self._sequence += 1
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            image_name = f"{stamp}_{self._sequence:03d}.jpg"
            image_path = self.directory / image_name
            metadata = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "confidence": round(confidence, 4),
                "bbox": list(bbox),
                "image": image_name,
                "sent_to_backend": False,
                "classification": None,
                "attempts": 0,
                "last_error": None,
            }
            if not cv2.imwrite(str(image_path), frame):
                raise RuntimeError(f"No se pudo guardar {image_name}")
            self._write(metadata)
            return metadata

    def update(self, metadata: dict) -> None:
        with self._lock:
            self._write(metadata)

    def load(self, image_name: str) -> dict:
        path = self._json_path(image_name)
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def pending(self) -> list[dict]:
        items = []
        with self._lock:
            for path in sorted(self.directory.glob("*.json")):
                data = json.loads(path.read_text(encoding="utf-8"))
                if not data.get("sent_to_backend"):
                    items.append(data)
        return items

    def image_path(self, image_name: str) -> Path:
        return self.directory / image_name

    def relative_image(self, image_name: str) -> str:
        return f"captures/{image_name}"

    def _json_path(self, image_name: str) -> Path:
        return self.directory / f"{Path(image_name).stem}.json"

    def _write(self, metadata: dict) -> None:
        path = self._json_path(metadata["image"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(metadata, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _last_sequence(self) -> int:
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_(\d+)\.jpg$")
        highest = 0
        for path in self.directory.glob("*.jpg"):
            match = pattern.match(path.name)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest
