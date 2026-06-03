from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import time

from keyboard_assistant.core.models import AppContext


EM_GETPASSWORDCHAR = 0x00D2


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class AppDetector:
    """Best-effort active app detector with a Windows implementation."""

    def __init__(self, cache_ttl_seconds: float = 0.25) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_context: AppContext | None = None
        self._cache_expires_at = 0.0

    def current_app(self) -> AppContext:
        now = time.monotonic()
        if self._cached_context is not None and now < self._cache_expires_at:
            return self._cached_context
        if not _is_windows_available():
            return AppContext()
        try:
            context = _current_windows_app()
        except OSError:
            context = AppContext()
        self._cached_context = context
        self._cache_expires_at = now + self.cache_ttl_seconds
        return context


def _is_windows_available() -> bool:
    return hasattr(ctypes, "windll")


def _current_windows_app() -> AppContext:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    _configure_win32_api(user32, kernel32)

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return AppContext()

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    title_buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buffer, 512)
    class_buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buffer, 256)
    focus = _focused_control(user32)

    process_name = ""
    access_query_limited_information = 0x1000
    process = kernel32.OpenProcess(access_query_limited_information, False, pid.value)
    if process:
        try:
            path_buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(path_buffer))
            query_full_process_image_name = ctypes.windll.kernel32.QueryFullProcessImageNameW
            if query_full_process_image_name(process, 0, path_buffer, ctypes.byref(size)):
                process_name = Path(path_buffer.value).name
        finally:
            kernel32.CloseHandle(process)

    return AppContext(
        app_name=process_name,
        app_identifier=process_name.lower(),
        window_title=title_buffer.value,
        window_class_name=class_buffer.value,
        field_type=focus["field_type"],
        field_name=focus["field_name"],
        is_password=focus["field_type"] == "password",
    )


def _configure_win32_api(user32: object, kernel32: object) -> None:
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, wintypes.LPVOID]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def _focused_control(user32: object) -> dict[str, str]:
    try:
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)) or not info.hwndFocus:
            return {"field_type": "", "field_name": ""}
        class_name = _window_class_name(user32, info.hwndFocus)
        password_char = int(user32.SendMessageW(info.hwndFocus, EM_GETPASSWORDCHAR, 0, 0))
        return {
            "field_type": classify_focused_control(class_name, password_char),
            "field_name": class_name,
        }
    except (AttributeError, OSError, ValueError):
        return {"field_type": "", "field_name": ""}


def _window_class_name(user32: object, hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    if not user32.GetClassNameW(hwnd, buffer, 256):
        return ""
    return buffer.value


def classify_focused_control(class_name: str, password_char: int = 0) -> str:
    normalized = class_name.strip().lower()
    if password_char:
        return "password"
    if normalized in {"edit", "richedit", "richedit20w", "richedit50w"}:
        return "text"
    if "terminal" in normalized:
        return "terminal"
    return ""
