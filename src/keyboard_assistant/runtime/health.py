from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeHealth:
    keyboard_hook_started: bool = False
    keyboard_hook_failed: bool = False
    overlay_started: bool = False
    overlay_failed: bool = False
    tray_icon_started: bool = False
    tray_icon_failed: bool = False
    database_opened: bool = False
    language_data_loaded: bool = False
    local_ai_enabled: bool = False
    local_ai_unavailable: bool = False
    assistant_status: str = "unknown"
    current_app: str = ""
    last_exception: str = ""
    events: list[str] = field(default_factory=list)

    def mark(self, event: str, **metadata: Any) -> None:
        self.events.append(event)
        for key, value in metadata.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def record_exception(self, component: str, exc: BaseException) -> None:
        self.last_exception = f"{component}: {type(exc).__name__}: {exc}"
        self.events.append(f"{component}_failed")

    def snapshot(self) -> dict[str, Any]:
        return {
            "keyboard_hook_started": self.keyboard_hook_started,
            "keyboard_hook_failed": self.keyboard_hook_failed,
            "overlay_started": self.overlay_started,
            "overlay_failed": self.overlay_failed,
            "tray_icon_started": self.tray_icon_started,
            "tray_icon_failed": self.tray_icon_failed,
            "database_opened": self.database_opened,
            "language_data_loaded": self.language_data_loaded,
            "local_ai_enabled": self.local_ai_enabled,
            "local_ai_unavailable": self.local_ai_unavailable,
            "assistant_status": self.assistant_status,
            "current_app": self.current_app,
            "last_exception": self.last_exception,
            "events": list(self.events[-20:]),
        }
