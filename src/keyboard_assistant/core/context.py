from __future__ import annotations

from dataclasses import dataclass
import re


WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*$")


@dataclass(frozen=True)
class TextContext:
    text: str
    current_word: str
    previous_words: tuple[str, ...]
    starts_new_sentence: bool
    has_double_space: bool


class TypedBuffer:
    """Fallback context tracker built only from recently typed characters."""

    def __init__(self, max_chars: int = 500) -> None:
        self.max_chars = max_chars
        self._chars: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self._chars)

    def push(self, char: str) -> None:
        if char == "\b":
            if self._chars:
                self._chars.pop()
            return
        self._chars.append(char)
        if len(self._chars) > self.max_chars:
            self._chars = self._chars[-self.max_chars :]

    def clear(self) -> None:
        self._chars.clear()

    def context(self) -> TextContext:
        return extract_text_context(self.text)


def extract_text_context(text: str, previous_word_limit: int = 5) -> TextContext:
    trimmed = text.rstrip()
    match = WORD_RE.search(trimmed)
    current_word = match.group(0) if match else ""
    before_word = trimmed[: match.start()] if match else trimmed
    words = tuple(re.findall(r"[A-Za-z][A-Za-z']*", before_word)[-previous_word_limit:])
    starts_new_sentence = _starts_new_sentence(before_word)
    return TextContext(
        text=text,
        current_word=current_word,
        previous_words=words,
        starts_new_sentence=starts_new_sentence,
        has_double_space="  " in text,
    )


def _starts_new_sentence(prefix: str) -> bool:
    stripped = prefix.rstrip()
    if not stripped:
        return True
    return stripped[-1] in ".!?"

