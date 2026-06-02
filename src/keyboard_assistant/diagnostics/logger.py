from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
from typing import Any


SENSITIVE_KEYS = {
    "text",
    "input_text",
    "original_text",
    "corrected_text",
    "suggestion_text",
    "replacement",
    "prompt",
    "response",
    "typed",
}
MAX_LOG_BYTES = 512_000
MAX_BACKUPS = 3


@dataclass(frozen=True)
class DiagnosticEvent:
    timestamp: str
    level: str
    event: str
    metadata: dict[str, Any]


class DiagnosticsLogger:
    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def info(self, event: str, **metadata: Any) -> None:
        self._write("info", event, metadata)

    def warning(self, event: str, **metadata: Any) -> None:
        self._write("warning", event, metadata)

    def error(self, event: str, **metadata: Any) -> None:
        self._write("error", event, metadata)

    def exception(self, event: str, exc: BaseException, **metadata: Any) -> None:
        metadata = dict(metadata)
        metadata["exception_type"] = type(exc).__name__
        metadata["traceback"] = _sanitize_traceback(exc)
        self._write("error", event, metadata)

    def read_events(self, limit: int = 50) -> list[DiagnosticEvent]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        events: list[DiagnosticEvent] = []
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(
                DiagnosticEvent(
                    timestamp=str(payload.get("timestamp", "")),
                    level=str(payload.get("level", "")),
                    event=str(payload.get("event", "")),
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        return events

    def clear(self) -> None:
        if self.log_path.exists():
            self.log_path.unlink()

    def _write(self, level: str, event: str, metadata: dict[str, Any]) -> None:
        self._rotate_if_needed()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "metadata": _sanitize_metadata(metadata),
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def _rotate_if_needed(self) -> None:
        if not self.log_path.exists() or self.log_path.stat().st_size < MAX_LOG_BYTES:
            return
        for index in range(MAX_BACKUPS - 1, 0, -1):
            source = self.log_path.with_suffix(self.log_path.suffix + f".{index}")
            target = self.log_path.with_suffix(self.log_path.suffix + f".{index + 1}")
            if source.exists():
                if target.exists():
                    target.unlink()
                source.rename(target)
        first = self.log_path.with_suffix(self.log_path.suffix + ".1")
        if first.exists():
            first.unlink()
        self.log_path.rename(first)


def default_log_path(database_path: str | Path) -> Path:
    path = Path(database_path)
    return path.with_suffix(".diagnostics.log")


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized = key.lower()
        if normalized in SENSITIVE_KEYS or normalized.endswith("_text"):
            clean[key] = "<redacted>"
        elif isinstance(value, dict):
            clean[key] = _sanitize_metadata(value)
        elif isinstance(value, (list, tuple)):
            clean[key] = [_sanitize_scalar(item) for item in value[:20]]
        else:
            clean[key] = _sanitize_scalar(value)
    return clean


def _sanitize_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 240:
            return value[:240] + "..."
        return value
    return repr(value)[:240]


def _sanitize_traceback(exc: BaseException) -> str:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return tb[-4000:]

