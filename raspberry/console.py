import threading

_lock = threading.Lock()


def console(*lines: str) -> None:
    text = "\n".join(lines)
    with _lock:
        print(text, flush=True)
