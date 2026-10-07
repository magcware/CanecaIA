from dataclasses import dataclass

import cv2
from ultralytics import YOLO


@dataclass(frozen=True)
class Detection:
    confidence: float
    bbox: tuple[int, int, int, int]
    label: str


class ObjectDetector:
    def __init__(self, model_path: str, image_size: int, confidence: float):
        self.model = YOLO(model_path)
        self.image_size = image_size
        self.confidence = confidence

    def detect(self, frame) -> list[Detection]:
        results = self.model.predict(
            frame,
            imgsz=self.image_size,
            conf=self.confidence,
            verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []

        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            detections.append(
                Detection(
                    confidence=float(box.conf[0]),
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    label=self.model.names.get(class_id, str(class_id)),
                )
            )
        detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections


def draw_detections(frame, detections: list[Detection]) -> None:
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (74, 255, 214), 3)
