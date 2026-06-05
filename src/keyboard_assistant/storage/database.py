from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from keyboard_assistant.core.models import AppProfile, AppearanceSettings, AssistantSettings, CorrectionRecord


DEFAULT_SETTINGS = {
    "assistant_enabled": "true",
    "correction_strength": "balanced",
    "learning_enabled": "true",
    "local_ai_enabled": "false",
    "local_ai_provider": "none",
    "local_ai_model": "",
    "local_ai_endpoint": "http://127.0.0.1:11434",
    "local_ai_timeout_seconds": "30.0",
    "appearance_theme": "dark",
    "suggestion_size": "medium",
    "suggestion_opacity": "94",
    "animations_enabled": "true",
}

VALID_CORRECTION_STRENGTHS = {"light", "balanced", "aggressive"}
VALID_ASSISTANT_STATUSES = {"on", "limited", "off"}
VALID_THEMES = {"light", "dark", "system"}
VALID_SUGGESTION_SIZES = {"small", "medium", "large"}


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            for key, value in DEFAULT_SETTINGS.items():
                connection.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as connection:
            connection.execute(sql, params)

    def get_settings(self) -> AssistantSettings:
        return AssistantSettings(
            assistant_enabled=self.get_bool_setting("assistant_enabled", True),
            correction_strength=self.get_setting("correction_strength", "balanced"),
            learning_enabled=self.get_bool_setting("learning_enabled", True),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        if key == "correction_strength" and value not in VALID_CORRECTION_STRENGTHS:
            raise ValueError(f"correction_strength must be one of: {', '.join(sorted(VALID_CORRECTION_STRENGTHS))}")
        if key == "appearance_theme" and value not in VALID_THEMES:
            raise ValueError(f"appearance_theme must be one of: {', '.join(sorted(VALID_THEMES))}")
        if key == "suggestion_size" and value not in VALID_SUGGESTION_SIZES:
            raise ValueError(f"suggestion_size must be one of: {', '.join(sorted(VALID_SUGGESTION_SIZES))}")
        if key == "suggestion_opacity":
            opacity = int(value)
            if opacity < 30 or opacity > 100:
                raise ValueError("suggestion_opacity must be between 30 and 100")
        self.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        value = self.get_setting(key, "true" if default else "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def set_bool_setting(self, key: str, value: bool) -> None:
        self.set_setting(key, "true" if value else "false")

    def get_appearance_settings(self) -> AppearanceSettings:
        return AppearanceSettings(
            theme=self.get_setting("appearance_theme", "dark"),
            suggestion_size=self.get_setting("suggestion_size", "medium"),
            opacity=int(self.get_setting("suggestion_opacity", "94")),
            animations_enabled=self.get_bool_setting("animations_enabled", True),
        )

    def set_appearance_settings(
        self,
        theme: str | None = None,
        suggestion_size: str | None = None,
        opacity: int | None = None,
        animations_enabled: bool | None = None,
    ) -> None:
        if theme is not None:
            self.set_setting("appearance_theme", theme)
        if suggestion_size is not None:
            self.set_setting("suggestion_size", suggestion_size)
        if opacity is not None:
            self.set_setting("suggestion_opacity", str(opacity))
        if animations_enabled is not None:
            self.set_bool_setting("animations_enabled", animations_enabled)

    def get_app_profile(self, app_identifier: str) -> AppProfile | None:
        if not app_identifier:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT app_name, app_identifier, assistant_status, correction_strength, learning_enabled
                FROM app_profiles
                WHERE lower(app_identifier) = lower(?)
                """,
                (app_identifier,),
            ).fetchone()
        if not row:
            return None
        return AppProfile(
            app_name=row["app_name"],
            app_identifier=row["app_identifier"],
            assistant_status=row["assistant_status"],
            correction_strength=row["correction_strength"],
            learning_enabled=bool(row["learning_enabled"]),
        )

    def list_app_profiles(self) -> list[AppProfile]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT app_name, app_identifier, assistant_status, correction_strength, learning_enabled
                FROM app_profiles
                ORDER BY lower(app_name), lower(app_identifier)
                """
            ).fetchall()
        return [
            AppProfile(
                app_name=row["app_name"],
                app_identifier=row["app_identifier"],
                assistant_status=row["assistant_status"],
                correction_strength=row["correction_strength"],
                learning_enabled=bool(row["learning_enabled"]),
            )
            for row in rows
        ]

    def upsert_app_profile(
        self,
        app_identifier: str,
        app_name: str | None = None,
        assistant_status: str | None = None,
        correction_strength: str | None = None,
        learning_enabled: bool | None = None,
    ) -> None:
        if not app_identifier:
            raise ValueError("app_identifier is required")
        existing = self.get_app_profile(app_identifier)
        resolved_name = app_name or (existing.app_name if existing else app_identifier)
        resolved_status = assistant_status or (existing.assistant_status if existing else "on")
        resolved_strength = correction_strength or (existing.correction_strength if existing else "balanced")
        resolved_learning = learning_enabled if learning_enabled is not None else (existing.learning_enabled if existing else True)
        if resolved_status not in VALID_ASSISTANT_STATUSES:
            raise ValueError(f"assistant_status must be one of: {', '.join(sorted(VALID_ASSISTANT_STATUSES))}")
        if resolved_strength not in VALID_CORRECTION_STRENGTHS:
            raise ValueError(f"correction_strength must be one of: {', '.join(sorted(VALID_CORRECTION_STRENGTHS))}")

        self.execute(
            """
            INSERT INTO app_profiles (
                app_name, app_identifier, assistant_status, correction_strength, learning_enabled, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(app_identifier) DO UPDATE SET
                app_name = excluded.app_name,
                assistant_status = excluded.assistant_status,
                correction_strength = excluded.correction_strength,
                learning_enabled = excluded.learning_enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (resolved_name, app_identifier.lower(), resolved_status, resolved_strength, int(resolved_learning)),
        )

    def remove_app_profile(self, app_identifier: str) -> None:
        self.execute("DELETE FROM app_profiles WHERE lower(app_identifier) = lower(?)", (app_identifier,))

    def record_accepted_suggestion(
        self,
        input_text: str,
        suggestion_text: str,
        suggestion_type: str,
        app_identifier: str = "",
    ) -> None:
        self.execute(
            """
            INSERT INTO accepted_suggestions (input_text, suggestion_text, suggestion_type, app_identifier)
            VALUES (?, ?, ?, ?)
            """,
            (input_text, suggestion_text, suggestion_type, app_identifier),
        )

    def record_correction_history(
        self,
        original_text: str,
        corrected_text: str,
        correction_type: str,
        confidence: float,
        app_identifier: str = "",
        accepted: bool = False,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO correction_history (
                    original_text, corrected_text, correction_type, confidence, app_identifier, accepted
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (original_text, corrected_text, correction_type, confidence, app_identifier, int(accepted)),
            )
            return int(cursor.lastrowid)

    def mark_correction_reverted(self, correction_id: int) -> None:
        self.execute(
            "UPDATE correction_history SET reverted = 1 WHERE id = ?",
            (correction_id,),
        )

    def record_reverted_correction(
        self,
        original_text: str,
        corrected_text: str,
        app_identifier: str = "",
    ) -> None:
        self.execute(
            """
            INSERT INTO reverted_corrections (original_text, corrected_text, app_identifier)
            VALUES (?, ?, ?)
            """,
            (original_text, corrected_text, app_identifier),
        )

    def latest_correction(self) -> CorrectionRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, original_text, corrected_text, correction_type, confidence, app_identifier
                FROM correction_history
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return CorrectionRecord(
            id=int(row["id"]),
            original_text=row["original_text"],
            corrected_text=row["corrected_text"],
            correction_type=row["correction_type"],
            confidence=float(row["confidence"]),
            app_identifier=row["app_identifier"],
        )

    def record_ignored_suggestion(
        self,
        input_text: str,
        suggestion_text: str,
        suggestion_type: str,
        app_identifier: str = "",
    ) -> None:
        self.execute(
            """
            INSERT INTO ignored_suggestions (input_text, suggestion_text, suggestion_type, app_identifier)
            VALUES (?, ?, ?, ?)
            """,
            (input_text, suggestion_text, suggestion_type, app_identifier),
        )

    def accepted_score(self, input_text: str, suggestion_text: str) -> float:
        count = self._count(
            "accepted_suggestions",
            "input_text = ? AND suggestion_text = ?",
            (input_text, suggestion_text),
        )
        return count * 0.02

    def ignored_score(self, input_text: str, suggestion_text: str) -> float:
        count = self._count(
            "ignored_suggestions",
            "input_text = ? AND suggestion_text = ?",
            (input_text, suggestion_text),
        )
        return count * 0.04

    def reverted_score(self, original_text: str, corrected_text: str) -> float:
        count = self._count(
            "reverted_corrections",
            "original_text = ? AND corrected_text = ?",
            (original_text, corrected_text),
        )
        return count * 0.05

    def add_personal_word(self, word: str, source: str = "manual", never_correct: bool = False) -> None:
        self.execute(
            """
            INSERT INTO personal_dictionary (word, source, frequency, never_correct)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(word) DO UPDATE SET
                frequency = personal_dictionary.frequency + 1,
                never_correct = excluded.never_correct,
                updated_at = CURRENT_TIMESTAMP
            """,
            (word, source, int(never_correct)),
        )

    def remove_personal_word(self, word: str) -> None:
        self.execute("DELETE FROM personal_dictionary WHERE lower(word) = lower(?)", (word,))

    def list_personal_words(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT word, source, frequency, never_correct, updated_at
                FROM personal_dictionary
                ORDER BY lower(word)
                """
            ).fetchall()

    def export_personal_dictionary(self, path: str | Path) -> int:
        rows = self.list_personal_words()
        payload = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "words": [
                {
                    "word": row["word"],
                    "source": row["source"],
                    "frequency": int(row["frequency"]),
                    "never_correct": bool(row["never_correct"]),
                }
                for row in rows
            ],
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return len(rows)

    def import_personal_dictionary(self, path: str | Path) -> int:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        words = _parse_dictionary_import_payload(payload)
        if not words:
            return 0

        with self.connect() as connection:
            for entry in words:
                connection.execute(
                    """
                    INSERT INTO personal_dictionary (word, source, frequency, never_correct, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(word) DO UPDATE SET
                        source = excluded.source,
                        frequency = max(personal_dictionary.frequency, excluded.frequency),
                        never_correct = CASE
                            WHEN personal_dictionary.never_correct = 1 OR excluded.never_correct = 1 THEN 1
                            ELSE 0
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        entry["word"],
                        entry["source"],
                        entry["frequency"],
                        int(entry["never_correct"]),
                    ),
                )
        return len(words)

    def is_never_correct_word(self, word: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT never_correct FROM personal_dictionary WHERE lower(word) = lower(?)",
                (word,),
            ).fetchone()
        return bool(row and row["never_correct"])

    def increment_word_frequency(self, word: str, app_identifier: str = "") -> int:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO word_frequency_user (word, frequency, app_identifier, last_used_at)
                VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(word, app_identifier) DO UPDATE SET
                    frequency = word_frequency_user.frequency + 1,
                    last_used_at = CURRENT_TIMESTAMP
                """,
                (word, app_identifier),
            )
            row = connection.execute(
                """
                SELECT frequency
                FROM word_frequency_user
                WHERE word = ? AND app_identifier = ?
                """,
                (word, app_identifier),
            ).fetchone()
        return int(row["frequency"])

    def word_frequency(self, word: str, app_identifier: str = "") -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT frequency
                FROM word_frequency_user
                WHERE word = ? AND app_identifier = ?
                """,
                (word, app_identifier),
            ).fetchone()
        return int(row["frequency"]) if row else 0

    def increment_phrase_frequency(self, phrase: str, app_identifier: str = "") -> None:
        normalized = " ".join(phrase.split())
        if not normalized:
            return
        self.execute(
            """
            INSERT INTO phrase_frequency (phrase, frequency, app_identifier, last_used_at)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phrase, app_identifier) DO UPDATE SET
                frequency = phrase_frequency.frequency + 1,
                last_used_at = CURRENT_TIMESTAMP
            """,
            (normalized, app_identifier),
        )

    def phrase_predictions(
        self,
        previous_words: tuple[str, ...],
        app_identifier: str = "",
        limit: int = 3,
    ) -> list[str]:
        if not previous_words:
            return []
        prefixes = [" ".join(previous_words[-length:]).lower() for length in range(min(3, len(previous_words)), 0, -1)]
        predictions: list[str] = []
        with self.connect() as connection:
            for prefix in prefixes:
                rows = connection.execute(
                    """
                    SELECT phrase
                    FROM phrase_frequency
                    WHERE lower(phrase) LIKE ?
                      AND (app_identifier = ? OR app_identifier = '')
                    ORDER BY frequency DESC, last_used_at DESC
                    LIMIT ?
                    """,
                    (prefix + " %", app_identifier, limit),
                ).fetchall()
                for row in rows:
                    words = str(row["phrase"]).split()
                    next_index = len(prefix.split())
                    if len(words) > next_index:
                        candidate = words[next_index]
                        if candidate not in predictions:
                            predictions.append(candidate)
                    if len(predictions) >= limit:
                        return predictions
        return predictions

    def clear_learning_data(self) -> None:
        with self.connect() as connection:
            for table in LEARNING_TABLES:
                connection.execute(f"DELETE FROM {table}")

    def data_summary(self) -> dict[str, int]:
        with self.connect() as connection:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
                for table in SUMMARY_TABLES
            }

    def get_model_settings(self) -> dict[str, str | bool]:
        return {
            "enabled": self.get_bool_setting("local_ai_enabled", False),
            "provider": self.get_setting("local_ai_provider", "none"),
            "model": self.get_setting("local_ai_model", ""),
            "endpoint": self.get_setting("local_ai_endpoint", "http://127.0.0.1:11434"),
            "timeout_seconds": self.get_setting("local_ai_timeout_seconds", "30.0"),
        }

    def set_model_settings(
        self,
        provider: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        if provider is not None:
            self.set_setting("local_ai_provider", provider)
        if model is not None:
            self.set_setting("local_ai_model", model)
        if enabled is not None:
            self.set_bool_setting("local_ai_enabled", enabled)
        if endpoint is not None:
            self.set_setting("local_ai_endpoint", endpoint)
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("local_ai_timeout_seconds must be positive")
            self.set_setting("local_ai_timeout_seconds", str(float(timeout_seconds)))

    def _count(self, table: str, where: str, params: tuple[Any, ...]) -> int:
        with self.connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE {where}", params).fetchone()
        return int(row["count"])


def _parse_dictionary_import_payload(payload: object) -> list[dict[str, str | int | bool]]:
    if isinstance(payload, dict):
        raw_words = payload.get("words")
    else:
        raw_words = payload
    if not isinstance(raw_words, list):
        raise ValueError("dictionary import must be a JSON object with a words list or a JSON list")

    entries: list[dict[str, str | int | bool]] = []
    for index, raw_entry in enumerate(raw_words, start=1):
        if isinstance(raw_entry, str):
            word = raw_entry.strip()
            source = "imported"
            frequency = 1
            never_correct = False
        elif isinstance(raw_entry, dict):
            word = str(raw_entry.get("word", "")).strip()
            source = str(raw_entry.get("source", "imported")).strip() or "imported"
            frequency = _positive_int(raw_entry.get("frequency", 1), f"words[{index}].frequency")
            never_correct = bool(raw_entry.get("never_correct", False))
        else:
            raise ValueError(f"words[{index}] must be a string or object")

        if not word:
            raise ValueError(f"words[{index}].word is required")
        entries.append(
            {
                "word": word,
                "source": source,
                "frequency": frequency,
                "never_correct": never_correct,
            }
        )
    return entries


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


LEARNING_TABLES = (
    "correction_history",
    "accepted_suggestions",
    "ignored_suggestions",
    "reverted_corrections",
    "phrase_frequency",
    "word_frequency_user",
)

SUMMARY_TABLES = (
    "app_profiles",
    "personal_dictionary",
    "correction_history",
    "accepted_suggestions",
    "ignored_suggestions",
    "reverted_corrections",
    "phrase_frequency",
    "word_frequency_user",
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    app_identifier TEXT NOT NULL UNIQUE,
    assistant_status TEXT NOT NULL DEFAULT 'on',
    correction_strength TEXT NOT NULL DEFAULT 'balanced',
    learning_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS personal_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'manual',
    frequency INTEGER NOT NULL DEFAULT 1,
    never_correct INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS correction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    correction_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    app_identifier TEXT NOT NULL DEFAULT '',
    accepted INTEGER NOT NULL DEFAULT 0,
    reverted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accepted_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_text TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    app_identifier TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ignored_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_text TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    app_identifier TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reverted_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    app_identifier TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS phrase_frequency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phrase TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    app_identifier TEXT NOT NULL DEFAULT '',
    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phrase, app_identifier)
);

CREATE TABLE IF NOT EXISTS word_frequency_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    app_identifier TEXT NOT NULL DEFAULT '',
    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word, app_identifier)
);

CREATE TABLE IF NOT EXISTS model_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'none',
    model_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS privacy_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
