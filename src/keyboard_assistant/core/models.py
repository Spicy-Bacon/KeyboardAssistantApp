from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AppContext:
    app_name: str = ""
    app_identifier: str = ""
    window_title: str = ""
    field_type: str = ""
    is_password: bool = False
    is_private: bool = False


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

