from __future__ import annotations

import ctypes
from ctypes import wintypes
import time


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_BACK = 0x08
ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class WindowsTextInjector:
    def __init__(self) -> None:
        if not _is_windows_available():
            raise RuntimeError("Text injection is only available on Windows.")
        self._configure_win32_api()

    def replace_previous_text(self, original_length: int, replacement: str) -> None:
        if not _is_windows_available():
            raise RuntimeError("Text injection is only available on Windows.")
        for _ in range(original_length):
            self._tap_virtual_key(VK_BACK)
        if replacement:
            self.type_text(replacement)

    def type_text(self, text: str) -> None:
        for char in text:
            self._tap_unicode(char)
            time.sleep(0.001)

    def _tap_virtual_key(self, vk_code: int) -> None:
        self._send_input(_keyboard_input(vk_code, 0, 0))
        self._send_input(_keyboard_input(vk_code, 0, KEYEVENTF_KEYUP))

    def _tap_unicode(self, char: str) -> None:
        code = ord(char)
        self._send_input(_keyboard_input(0, code, KEYEVENTF_UNICODE))
        self._send_input(_keyboard_input(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))

    def _send_input(self, event: INPUT) -> None:
        sent = ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ctypes.WinError()

    def _configure_win32_api(self) -> None:
        ctypes.windll.user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        ctypes.windll.user32.SendInput.restype = wintypes.UINT


class NullTextInjector:
    """No-op injector used by tests and explicit safe-mode fallback."""

    def __init__(self) -> None:
        self.replacements: list[tuple[int, str]] = []
        self.typed_text: list[str] = []

    def replace_previous_text(self, original_length: int, replacement: str) -> None:
        self.replacements.append((original_length, replacement))

    def type_text(self, text: str) -> None:
        self.typed_text.append(text)


def _keyboard_input(vk_code: int, scan_code: int, flags: int) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.union.ki = KEYBDINPUT(vk_code, scan_code, flags, 0, 0)
    return event


def _is_windows_available() -> bool:
    return hasattr(ctypes, "windll")
