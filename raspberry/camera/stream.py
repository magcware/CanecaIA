import cv2


class CameraStream:
    def __init__(self, index: int):
        self.index = index
        self._capture = None

    def open(self) -> None:
        capture = cv2.VideoCapture(self.index)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"No se pudo abrir la cámara {self.index}"
            )
        self._capture = capture

    def read(self):
        if self._capture is None:
            raise RuntimeError("La cámara no está inicializada")
        ok, frame = self._capture.read()
        if not ok:
            return None
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
