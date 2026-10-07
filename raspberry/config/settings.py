import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _raw(name: str):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _float(name: str, default: float) -> float:
    value = _raw(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un número") from exc


def _int(name: str, default: int) -> int:
    value = _raw(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un entero") from exc


@dataclass(frozen=True)
class Settings:
    backend_url: str
    confidence_threshold: float
    consecutive_frames: int
    cooldown_seconds: float
    request_timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    camera_index: int
    yolo_model: str
    yolo_imgsz: int
    captures_dir: Path
    root: Path = ROOT


def load_settings() -> Settings:
    captures = _raw("CAPTURES_DIR") or "captures"
    captures_dir = Path(captures)
    if not captures_dir.is_absolute():
        captures_dir = ROOT / captures_dir

    settings = Settings(
        backend_url=(_raw("BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/"),
        confidence_threshold=_float("CONFIDENCE_THRESHOLD", 0.80),
        consecutive_frames=_int("CONSECUTIVE_FRAMES", 3),
        cooldown_seconds=_float("COOLDOWN_SECONDS", 3),
        request_timeout_seconds=_float("REQUEST_TIMEOUT_SECONDS", 60),
        max_retries=_int("MAX_RETRIES", 3),
        retry_backoff_seconds=_float("RETRY_BACKOFF_SECONDS", 5),
        camera_index=_int("CAMERA_INDEX", 0),
        yolo_model=_raw("YOLO_MODEL") or "yolov8n.pt",
        yolo_imgsz=_int("YOLO_IMGSZ", 640),
        captures_dir=captures_dir,
    )
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if not 0 < settings.confidence_threshold <= 1:
        raise ValueError("CONFIDENCE_THRESHOLD debe estar entre 0 y 1")
    if settings.consecutive_frames < 1:
        raise ValueError("CONSECUTIVE_FRAMES debe ser al menos 1")
    if settings.cooldown_seconds < 0:
        raise ValueError("COOLDOWN_SECONDS no puede ser negativo")
    if settings.request_timeout_seconds <= 0:
        raise ValueError("REQUEST_TIMEOUT_SECONDS debe ser mayor que 0")
    if settings.max_retries < 1:
        raise ValueError("MAX_RETRIES debe ser al menos 1")
    if settings.retry_backoff_seconds < 0:
        raise ValueError("RETRY_BACKOFF_SECONDS no puede ser negativo")
    if settings.yolo_imgsz < 32:
        raise ValueError("YOLO_IMGSZ debe ser al menos 32")


def resolve_model_path(settings: Settings) -> str:
    configured = Path(settings.yolo_model)
    if configured.is_file():
        return str(configured)
    local = settings.root / settings.yolo_model
    if local.is_file():
        return str(local)
    return settings.yolo_model
