from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import threading
from typing import Callable


WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_CAPITAL = 0x14
LLKHF_INJECTED = 0x10

DIGIT_SHIFT = {
    "0": ")",
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
}

PUNCTUATION_KEYS = {
    0xBA: (";", ":"),
    0xBB: ("=", "+"),
    0xBC: (",", "<"),
    0xBD: ("-", "_"),
    0xBE: (".", ">"),
    0xBF: ("/", "?"),
    0xC0: ("`", "~"),
    0xDB: ("[", "{"),
    0xDC: ("\\", "|"),
    0xDD: ("]", "}"),
    0xDE: ("'", '"'),
}


@dataclass(frozen=True)
class KeyboardEvent:
    key: str
    char: str = ""
    alt: bool = False
    ctrl: bool = False
    shift: bool = False


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
) if hasattr(ctypes, "WINFUNCTYPE") else None


class WindowsKeyboardListener:
    """Low-level Windows keyboard hook.

    The callback may return True to suppress the original key event.
    """

    def __init__(
        self,
        on_event: Callable[[KeyboardEvent], bool | None],
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        if not hasattr(ctypes, "windll") or LowLevelKeyboardProc is None:
            raise RuntimeError("Windows keyboard hooks are only available on Windows.")
        self.on_event = on_event
        self.on_error = on_error
        self.callback_error_count = 0
        self._hook: int | None = None
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._startup_error: BaseException | None = None
        self._callback_ref = LowLevelKeyboardProc(self._handle_event)
        self._configure_win32_api()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._started_event.clear()
        self._startup_error = None
        self._thread = threading.Thread(target=self._message_loop, name="keyboard-hook", daemon=True)
        self._thread.start()
        self._started_event.wait(timeout=3)
        if self._startup_error:
            raise RuntimeError("failed to install Windows keyboard hook") from self._startup_error

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    def _message_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            self._thread_id = kernel32.GetCurrentThreadId()
            module = kernel32.GetModuleHandleW(None)
            self._hook = self._set_keyboard_hook(module)
            if not self._hook:
                self._hook = self._set_keyboard_hook(None)
            if not self._hook:
                raise ctypes.WinError()
        except BaseException as exc:
            self._startup_error = exc
            self._started_event.set()
            return
        self._started_event.set()
        try:
            message = wintypes.MSG()
            while not self._stop_event.is_set() and user32.GetMessageW(ctypes.byref(message), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
                self._hook = None

    def _set_keyboard_hook(self, module: int | None) -> int:
        return int(
            ctypes.windll.user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._callback_ref,
                module,
                0,
            )
            or 0
        )

    def _configure_win32_api(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        HHOOK = wintypes.HANDLE
        HINSTANCE = getattr(wintypes, "HINSTANCE", wintypes.HANDLE)
        HOOKPROC = LowLevelKeyboardProc

        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = HINSTANCE

        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = HHOOK
        user32.UnhookWindowsHookEx.argtypes = [HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostThreadMessageW.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = wintypes.LPARAM

    def _handle_event(self, n_code: int, w_param: int, l_param: int) -> int:
        user32 = ctypes.windll.user32
        if n_code < 0 or w_param not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if info.flags & LLKHF_INJECTED:
            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        event = self._to_event(info.vkCode, info.scanCode)
        suppress = bool(event and self._dispatch_event_safely(event))
        if suppress:
            return 1
        return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

    def _dispatch_event_safely(self, event: KeyboardEvent | None) -> bool:
        if event is None:
            return False
        try:
            return bool(self.on_event(event))
        except Exception as exc:
            self.callback_error_count += 1
            if self.on_error:
                self.on_error(exc)
            return False

    def _to_event(self, vk_code: int, scan_code: int) -> KeyboardEvent | None:
        alt = _is_key_down(VK_MENU)
        ctrl = _is_key_down(VK_CONTROL)
        shift = _is_key_down(VK_SHIFT)

        special = {
            VK_BACK: "backspace",
            VK_TAB: "tab",
            VK_RETURN: "enter",
            VK_ESCAPE: "escape",
            VK_SPACE: "space",
            VK_LEFT: "left",
            VK_UP: "up",
            VK_RIGHT: "right",
            VK_DOWN: "down",
        }.get(vk_code)
        if special:
            return KeyboardEvent(key=special, char=" " if special == "space" else "", alt=alt, ctrl=ctrl, shift=shift)

        char = _vk_to_char(vk_code, scan_code, shift=shift)
        if not char:
            return None
        key = char.lower() if alt or ctrl else "char"
        return KeyboardEvent(key=key, char=char, alt=alt, ctrl=ctrl, shift=shift)


def _is_key_down(vk_code: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


def _vk_to_char(vk_code: int, scan_code: int, shift: bool = False) -> str:
    user32 = ctypes.windll.user32
    state = (ctypes.c_ubyte * 256)()
    has_keyboard_state = bool(user32.GetKeyboardState(ctypes.byref(state)))
    if has_keyboard_state and shift:
        state[VK_SHIFT] = 0x80
    if has_keyboard_state:
        fallback = _fallback_vk_to_char(vk_code, shift)
    else:
        fallback = _fallback_vk_to_char(vk_code, shift)
        if fallback:
            return fallback
        return ""
    buffer = ctypes.create_unicode_buffer(8)
    layout = user32.GetKeyboardLayout(0)
    result = user32.ToUnicodeEx(vk_code, scan_code, state, buffer, len(buffer), 0, layout)
    if result <= 0:
        return fallback
    return buffer.value[:result]


def _fallback_vk_to_char(vk_code: int, shift: bool = False) -> str:
    if 0x41 <= vk_code <= 0x5A:
        char = chr(vk_code).lower()
        caps = _is_caps_lock_on()
        return char.upper() if shift ^ caps else char
    if 0x30 <= vk_code <= 0x39:
        char = chr(vk_code)
        return DIGIT_SHIFT[char] if shift else char
    punctuation = PUNCTUATION_KEYS.get(vk_code)
    if punctuation:
        return punctuation[1] if shift else punctuation[0]
    return ""


def _is_caps_lock_on() -> bool:
    try:
        return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 0x0001)
    except AttributeError:
        return False
