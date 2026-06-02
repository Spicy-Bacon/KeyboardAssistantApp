from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenPoint:
    x: int
    y: int


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


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
        ("rcCaret", RECT),
    ]


class CursorLocator:
    def current_anchor(self) -> ScreenPoint:
        if hasattr(ctypes, "windll"):
            point = self._windows_caret_anchor()
            if point:
                return point
        return self._cursor_position()

    def _windows_caret_anchor(self) -> ScreenPoint | None:
        user32 = ctypes.windll.user32
        _configure_user32(user32)
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
            return None
        if not info.hwndCaret:
            return None

        point = wintypes.POINT(info.rcCaret.left, info.rcCaret.bottom)
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(point)):
            return None
        return ScreenPoint(point.x, point.y)

    def _cursor_position(self) -> ScreenPoint:
        if hasattr(ctypes, "windll"):
            _configure_user32(ctypes.windll.user32)
            point = wintypes.POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                return ScreenPoint(point.x, point.y)
        return ScreenPoint(100, 100)


def _configure_user32(user32: object) -> None:
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, wintypes.LPVOID]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
