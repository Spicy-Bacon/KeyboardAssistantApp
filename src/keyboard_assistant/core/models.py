from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AppContext:
    app_name: str = ""
    app_identifier: str = ""
    window_title: str = ""
    window_class_name: str = ""
    field_type: str = ""
    field_name: str = ""
    is_password: bool = False
    is_private: bool = False


@dataclass(frozen=True)
class AssistantSettings:
    assistant_enabled: bool = True
    correction_strength: str = "balanced"
    learning_enabled: bool = True


@dataclass(frozen=True)
class AppProfile:
    app_name: str
    app_identifier: str
    assistant_status: str = "on"
    correction_strength: str = "balanced"
    learning_enabled: bool = True


@dataclass(frozen=True)
class AppearanceSettings:
    theme: str = "dark"
    suggestion_size: str = "medium"
    opacity: int = 94
    animations_enabled: bool = True


@dataclass(frozen=True)
class Suggestion:
    original: str
    replacement: str
    kind: str
    confidence: float
    auto_apply: bool = False

    def with_confidence(self, confidence: float, auto_apply: bool | None = None) -> "Suggestion":
        return replace(
            self,
            confidence=confidence,
            auto_apply=self.auto_apply if auto_apply is None else auto_apply,
        )


@dataclass(frozen=True)
class CorrectionRecord:
    id: int
    original_text: str
    corrected_text: str
    correction_type: str
    confidence: float
    app_identifier: str = ""
