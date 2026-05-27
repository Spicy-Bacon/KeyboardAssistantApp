from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator


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

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as connection:
            connection.execute(sql, params)

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

    def is_never_correct_word(self, word: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT never_correct FROM personal_dictionary WHERE lower(word) = lower(?)",
                (word,),
            ).fetchone()
        return bool(row and row["never_correct"])

    def increment_word_frequency(self, word: str, app_identifier: str = "") -> None:
        self.execute(
            """
            INSERT INTO word_frequency_user (word, frequency, app_identifier, last_used_at)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(word, app_identifier) DO UPDATE SET
                frequency = word_frequency_user.frequency + 1,
                last_used_at = CURRENT_TIMESTAMP
            """,
            (word, app_identifier),
        )

    def clear_learning_data(self) -> None:
        with self.connect() as connection:
            for table in LEARNING_TABLES:
                connection.execute(f"DELETE FROM {table}")

    def _count(self, table: str, where: str, params: tuple[Any, ...]) -> int:
        with self.connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE {where}", params).fetchone()
        return int(row["count"])


LEARNING_TABLES = (
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
