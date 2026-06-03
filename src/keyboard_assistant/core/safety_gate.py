from __future__ import annotations

import re

from keyboard_assistant.core.candidate_generator import Candidate
from keyboard_assistant.core.models import AppContext, Suggestion
from keyboard_assistant.data.defaults import COMMON_WORDS
from keyboard_assistant.storage.database import Database


PROTECTED_VALID_WORDS = {
    "accept",
    "advice",
    "advise",
    "affect",
    "apple",
    "class",
    "effect",
    "except",
    "form",
    "from",
    "function",
    "hell",
    "ill",
    "import",
    "loose",
    "lose",
    "public",
    "return",
    "shell",
    "static",
    "string",
    "than",
    "then",
    "well",
    "were",
}

CODE_KEYWORDS = {
    "class",
    "const",
    "def",
    "else",
    "false",
    "for",
    "from",
    "function",
    "if",
    "import",
    "let",
    "none",
    "null",
    "package",
    "private",
    "protected",
    "public",
    "return",
    "static",
    "true",
    "var",
    "void",
    "while",
}

RISKY_APP_HINTS = {
    "cmd.exe",
    "code.exe",
    "devenv.exe",
    "powershell.exe",
    "pwsh.exe",
    "pycharm",
    "rider",
    "terminal",
    "windowsterminal.exe",
}

URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
FILE_NAME_RE = re.compile(r"\b[\w.-]+\.(?:py|js|ts|tsx|jsx|json|md|txt|yaml|yml|toml|ini|cfg|exe|dll)\b", re.I)
CAMEL_OR_PASCAL_RE = re.compile(r"\b[A-Za-z]+[A-Z][A-Za-z]*\b")


class AutoApplySafetyGate:
    """Final conservative decision point for auto-apply behavior."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def allow_auto_apply(
        self,
        candidate: Candidate,
        score: float,
        app_context: AppContext | None = None,
        correction_strength: str = "balanced",
        source_text: str = "",
        minimum_score: float = 0.92,
    ) -> bool:
        app_context = app_context or AppContext()
        if not candidate.should_auto_apply or score < minimum_score:
            return False
        if correction_strength == "light":
            return False
        if _looks_code_like(source_text or candidate.original_text):
            return False
        if _is_risky_app_context(app_context):
            return False
        if self.database.ignored_score(candidate.original_text, candidate.suggestion_text) > 0:
            return False
        if self.database.reverted_score(candidate.original_text, candidate.suggestion_text) > 0:
            return False

        suggestion_type = candidate.suggestion_type
        if suggestion_type in {"phrase_prediction", "user_phrase_prediction", "local_ai"}:
            return False
        if suggestion_type == "typo":
            return _is_safe_exact_typo(candidate)
        if suggestion_type == "contraction":
            return candidate.metadata.get("category") == "safe_auto" and not _is_protected_word(candidate)
        if suggestion_type == "capitalization":
            rule = candidate.metadata.get("rule")
            if rule == "standalone_i":
                return True
            return rule == "sentence_start" and not _is_protected_word(candidate)
        if suggestion_type == "confusion_pair":
            return bool(candidate.metadata.get("safe_phrase")) and score >= max(minimum_score, 0.94)
        return False

    def allow_suggestion_auto_apply(self, suggestion: Suggestion, source_text: str = "") -> bool:
        if suggestion.kind in {"next_word", "local_ai"}:
            return False
        if _looks_code_like(source_text or suggestion.original):
            return False
        return suggestion.auto_apply


def _is_safe_exact_typo(candidate: Candidate) -> bool:
    original = candidate.original_text.lower()
    replacement = candidate.suggestion_text.lower().strip("'")
    if candidate.source != "common_typos":
        return False
    if not original.isalpha():
        return False
    if _is_protected_word(candidate):
        return False
    if original in COMMON_WORDS:
        return False
    return bool(replacement and replacement in COMMON_WORDS)


def _is_protected_word(candidate: Candidate) -> bool:
    original_words = {word.lower().strip("'") for word in candidate.original_text.split() if word}
    return bool(original_words & PROTECTED_VALID_WORDS)


def _is_risky_app_context(app_context: AppContext) -> bool:
    haystack = " ".join(
        [
            app_context.app_identifier,
            app_context.app_name,
            app_context.window_title,
            app_context.window_class_name,
            app_context.field_type,
            app_context.field_name,
        ]
    ).lower()
    return any(hint in haystack for hint in RISKY_APP_HINTS)


def _looks_code_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if URL_RE.search(stripped) or EMAIL_RE.search(stripped) or FILE_NAME_RE.search(stripped):
        return True
    if stripped.startswith(("-", "/", "\\")) and not stripped.startswith(("'", '"')):
        return True
    if "\\" in stripped or "/" in stripped:
        return True
    if "_" in stripped:
        return True
    if re.search(r"\b[A-Za-z]+-[A-Za-z0-9-]+\b", stripped):
        return True
    if CAMEL_OR_PASCAL_RE.search(stripped):
        return True
    if any(symbol in stripped for symbol in ("{", "}", "[", "]", "(", ")", ";", "=>", "==", "!=")):
        return True
    words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z']*", stripped)}
    if len(words & CODE_KEYWORDS) >= 2:
        return True
    return bool(words & CODE_KEYWORDS and any(symbol in stripped for symbol in (":", ".", "=")))


def looks_code_like_text(text: str) -> bool:
    return _looks_code_like(text)
