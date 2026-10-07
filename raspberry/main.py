import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from camera.stream import CameraStream
from capture.store import CaptureStore
from capture.uploader import BackendUploader
from config.settings import load_settings, resolve_model_path
from console import console
from detection.tracker import DetectionTracker
from kiosk.display import KioskApp
from yolo.detector import ObjectDetector, draw_detections


def main() -> None:
    settings = load_settings()
    console(
        "=====================================",
        " CANECAS INTELIGENTES",
        " Raspberry Pi + YOLO",
        "=====================================",
        "",
        "Inicializando cámara...",
    )
    camera = CameraStream(settings.camera_index)
    camera.open()
    console("Cámara OK", "", "Inicializando YOLO...")

    detector = ObjectDetector(
        resolve_model_path(settings),
        settings.yolo_imgsz,
        settings.confidence_threshold,
    )
    console("YOLO OK", "", "Iniciando detección...", "")

    store = CaptureStore(settings.captures_dir)
    uploader = BackendUploader(settings, store)
    tracker = DetectionTracker(
        settings.consecutive_frames,
        settings.cooldown_seconds,
    )
    kiosk = KioskApp()
    uploader.on_success = kiosk.show_result
    uploader.on_failure = kiosk.show_failure

    try:
        kiosk.start()
        uploader.start()
        console("Ctrl+C detiene el programa.", "")
        while True:
            frame = camera.read()
            if frame is None:
                time.sleep(0.05)
                continue

            detections = detector.detect(frame)
            best = detections[0] if detections else None
            confirmed = tracker.observe(best is not None)
            if tracker.streak == 1 and best is not None:
                console(
                    "Objeto detectado",
                    f"Confidence: {best.confidence:.2f}",
                    "",
                )
            snapshot = frame.copy()
            draw_detections(frame, detections)
            if confirmed and best is not None:
                console("Objeto confirmado", "Capturando imagen...", "")
                metadata = store.save(snapshot, best.confidence, best.bbox)
                kiosk.show_capture(store.image_path(metadata["image"]))
                console(
                    "Imagen guardada:",
                    store.relative_image(metadata["image"]),
                    "",
                )
                uploader.submit(metadata["image"])
                console(f"Cooldown: {settings.cooldown_seconds:g} segundos", "")

            _publish(kiosk, frame)
    except KeyboardInterrupt:
        console("", "Detenido.")
    finally:
        kiosk.stop()
        uploader.stop()
        camera.close()


def _publish(kiosk: KioskApp, frame) -> None:
    view = frame
    height, width = frame.shape[:2]
    if width > 1280:
        scale = 1280 / width
        view = cv2.resize(
            frame,
            (1280, int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(
        ".jpg",
        view,
        [int(cv2.IMWRITE_JPEG_QUALITY), 80],
    )
    if ok:
        kiosk.publish_frame(encoded.tobytes())


if __name__ == "__main__":
    main()
