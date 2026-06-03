from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
import queue

from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.core.models import AppearanceSettings


WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_LBUTTONDOWN = 0x0201
WM_APP_DRAIN_QUEUE = 0x8001
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
LWA_ALPHA = 0x00000002
DT_LEFT = 0x00000000
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
DEFAULT_CHARSET = 1
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
CLEARTYPE_QUALITY = 5
DEFAULT_PITCH = 0
FW_NORMAL = 400
FONT_FACE = "Segoe UI"
THEMES = {
    "dark": {
        "text_primary": 0x00F2F2F2,
        "text_secondary": 0x00B8B8B8,
        "background": 0x00242424,
        "highlight_background": 0x003A3A3A,
    },
    "light": {
        "text_primary": 0x001F2937,
        "text_secondary": 0x004B5563,
        "background": 0x00F9FAFB,
        "highlight_background": 0x00E5E7EB,
    },
    "system": {
        "text_primary": 0x00F2F2F2,
        "text_secondary": 0x00B8B8B8,
        "background": 0x00242424,
        "highlight_background": 0x003A3A3A,
    },
}
OVERLAY_RADIUS_MM = 2.0
SIZE_CONFIG = {
    "small": {"height": 30, "font_height": -13, "char_width": 7, "padding": 22, "min_choice_width": 96},
    "medium": {"height": 36, "font_height": -15, "char_width": 8, "padding": 26, "min_choice_width": 128},
    "large": {"height": 44, "font_height": -17, "char_width": 10, "padding": 30, "min_choice_width": 156},
}


WndProc = (
    ctypes.WINFUNCTYPE(
        wintypes.LPARAM,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    if hasattr(ctypes, "WINFUNCTYPE")
    else None
)

HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HINSTANCE = getattr(wintypes, "HINSTANCE", wintypes.HANDLE)
HMENU = getattr(wintypes, "HMENU", wintypes.HANDLE)
HFONT = getattr(wintypes, "HFONT", wintypes.HANDLE)
HGDIOBJ = getattr(wintypes, "HGDIOBJ", wintypes.HANDLE)
HRGN = getattr(wintypes, "HRGN", wintypes.HANDLE)


if WndProc is not None:
    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WndProc),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", HINSTANCE),
            ("hIcon", HICON),
            ("hCursor", HCURSOR),
            ("hbrBackground", HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]


    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [
            ("hdc", wintypes.HDC),
            ("fErase", wintypes.BOOL),
            ("rcPaint", wintypes.RECT),
            ("fRestore", wintypes.BOOL),
            ("fIncUpdate", wintypes.BOOL),
            ("rgbReserved", ctypes.c_byte * 32),
        ]
else:
    WNDCLASS = None
    PAINTSTRUCT = None


class SuggestionOverlay:
    """Small native Win32 overlay for visible suggestion candidates."""

    def __init__(
        self,
        on_close: Callable[[], None] | None = None,
        on_select: Callable[[int], None] | None = None,
    ) -> None:
        if not _is_windows_overlay_available():
            raise RuntimeError("Suggestion overlay is currently Windows-only.")

        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.kernel32 = ctypes.windll.kernel32
        self._configure_win32_api()
        self.on_close = on_close
        self.on_select = on_select
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._labels: list[str] = []
        self._focus_index = 0
        self._choice_bounds: list[tuple[int, int]] = []
        self._appearance = AppearanceSettings()
        self._closed = False
        self._wnd_proc_ref = WndProc(self._wnd_proc)
        self._class_name = f"KeyboardAssistantSuggestionOverlay{id(self)}"
        self._class_registered = False
        self._register_class()
        self.hwnd = self._create_window()
        self.apply_appearance(self._appearance)
        self.user32.ShowWindow(self.hwnd, SW_HIDE)

    def run(self) -> None:
        message = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(message), 0, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(message))
            self.user32.DispatchMessageW(ctypes.byref(message))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if getattr(self, "hwnd", None):
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._class_registered:
            self.user32.UnregisterClassW(self._class_name, self.kernel32.GetModuleHandleW(None))
            self._class_registered = False

    def call_soon(self, callback: Callable[[], None]) -> None:
        self._queue.put(callback)
        if getattr(self, "hwnd", None):
            self.user32.PostMessageW(self.hwnd, WM_APP_DRAIN_QUEUE, 0, 0)

    def show_suggestions(self, suggestions: list[Suggestion], x: int, y: int, focus_index: int = 0) -> None:
        self._focus_index = max(0, min(focus_index, max(0, len(suggestions[:3]) - 1)))
        self._labels = [
            _format_label(index, suggestion, self._focus_index)
            for index, suggestion in enumerate(suggestions[:3])
        ]
        self._choice_bounds = _choice_bounds(self._labels, self._appearance)
        width = _measure_width(self._labels, self._appearance)
        height = _size_config(self._appearance)["height"]
        screen_width = self.user32.GetSystemMetrics(0)
        screen_height = self.user32.GetSystemMetrics(1)
        pos_x, pos_y = calculate_overlay_position(x, y, width, height, screen_width, screen_height)
        self.user32.MoveWindow(self.hwnd, pos_x, pos_y, width, height, True)
        self._round_window(width, height)
        self.user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        self.user32.InvalidateRect(self.hwnd, None, True)

    def apply_appearance(self, appearance: AppearanceSettings) -> None:
        self._appearance = appearance
        if getattr(self, "hwnd", None):
            alpha = max(30, min(100, appearance.opacity))
            self.user32.SetLayeredWindowAttributes(self.hwnd, 0, int(alpha * 255 / 100), LWA_ALPHA)
            self.user32.InvalidateRect(self.hwnd, None, True)

    def hide(self) -> None:
        if getattr(self, "hwnd", None):
            self.user32.ShowWindow(self.hwnd, SW_HIDE)

    def _register_class(self) -> None:
        if self._class_registered:
            return
        if WNDCLASS is None:
            raise RuntimeError("Suggestion overlay is currently Windows-only.")

        instance = self.kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASS()
        wndclass.lpfnWndProc = self._wnd_proc_ref
        wndclass.hInstance = instance
        wndclass.lpszClassName = self._class_name
        wndclass.hbrBackground = self.gdi32.CreateSolidBrush(_theme(self._appearance)["background"])
        atom = self.user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            error = self.kernel32.GetLastError()
            if error != 1410:
                raise ctypes.WinError(error)
        self._class_registered = True

    def _configure_win32_api(self) -> None:
        self.user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.DefWindowProcW.restype = wintypes.LPARAM
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            HMENU,
            HINSTANCE,
            wintypes.LPVOID,
        ]
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.SetLayeredWindowAttributes.argtypes = [
            wintypes.HWND,
            wintypes.COLORREF,
            ctypes.c_byte,
            wintypes.DWORD,
        ]
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostMessageW.restype = wintypes.BOOL
        self.user32.SetWindowRgn.argtypes = [wintypes.HWND, HRGN, wintypes.BOOL]
        self.user32.SetWindowRgn.restype = ctypes.c_int
        if hasattr(self.user32, "GetDpiForWindow"):
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user32.GetDpiForWindow.restype = wintypes.UINT
        self.user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]
        self.user32.UnregisterClassW.restype = wintypes.BOOL
        self.gdi32.CreateFontW.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPCWSTR,
        ]
        self.gdi32.CreateFontW.restype = HFONT
        self.gdi32.CreateRoundRectRgn.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.gdi32.CreateRoundRectRgn.restype = HRGN
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, HGDIOBJ]
        self.gdi32.SelectObject.restype = HGDIOBJ
        self.gdi32.DeleteObject.argtypes = [HGDIOBJ]
        self.gdi32.DeleteObject.restype = wintypes.BOOL

    def _create_window(self) -> int:
        ex_style = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE
        hwnd = self.user32.CreateWindowExW(
            ex_style,
            self._class_name,
            "Keyboard Assistant",
            WS_POPUP,
            0,
            0,
            260,
            34,
            0,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _wnd_proc(self, hwnd: int, message: int, w_param: int, l_param: int) -> int:
        if message == WM_APP_DRAIN_QUEUE:
            self._drain_queue()
            return 0
        if message == WM_PAINT:
            self._paint(hwnd)
            return 0
        if message == WM_LBUTTONDOWN:
            index = choice_index_at_x(self._choice_bounds, l_param & 0xFFFF)
            if index is not None and self.on_select:
                self.on_select(index)
            return 0
        if message == WM_CLOSE:
            self.close()
            return 0
        if message == WM_DESTROY:
            if self.on_close:
                callback = self.on_close
                self.on_close = None
                callback()
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, message, w_param, l_param)

    def _drain_queue(self) -> None:
        while True:
            try:
                callback = self._queue.get_nowait()
            except queue.Empty:
                break
            callback()

    def _paint(self, hwnd: int) -> None:
        if PAINTSTRUCT is None:
            raise RuntimeError("Suggestion overlay is currently Windows-only.")
        paint = PAINTSTRUCT()
        hdc = self.user32.BeginPaint(hwnd, ctypes.byref(paint))
        try:
            rect = wintypes.RECT()
            self.user32.GetClientRect(hwnd, ctypes.byref(rect))
            theme = _theme(self._appearance)
            config = _size_config(self._appearance)
            brush = self.gdi32.CreateSolidBrush(theme["background"])
            self.user32.FillRect(hdc, ctypes.byref(rect), brush)
            self.gdi32.DeleteObject(brush)
            self.gdi32.SetBkMode(hdc, 1)
            font = self._create_text_font(config)
            previous_font = self.gdi32.SelectObject(hdc, font) if font else None

            for index, label in enumerate(self._labels):
                label_width = _label_width(label, config)
                x = self._choice_bounds[index][0] if index < len(self._choice_bounds) else 10
                label_rect = wintypes.RECT(x, 0, x + label_width, config["height"])
                if index == self._focus_index:
                    highlight = self.gdi32.CreateSolidBrush(theme["highlight_background"])
                    self.user32.FillRect(hdc, ctypes.byref(label_rect), highlight)
                    self.gdi32.DeleteObject(highlight)
                self.gdi32.SetTextColor(hdc, theme["text_primary"] if index == self._focus_index else theme["text_secondary"])
                self.user32.DrawTextW(hdc, label, -1, ctypes.byref(label_rect), DT_LEFT | DT_VCENTER | DT_SINGLELINE)
        finally:
            if "previous_font" in locals() and previous_font:
                self.gdi32.SelectObject(hdc, previous_font)
            if "font" in locals() and font:
                self.gdi32.DeleteObject(font)
            self.user32.EndPaint(hwnd, ctypes.byref(paint))

    def _create_text_font(self, config: dict[str, int]) -> int:
        return self.gdi32.CreateFontW(
            config["font_height"],
            0,
            0,
            0,
            FW_NORMAL,
            0,
            0,
            0,
            DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS,
            CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY,
            DEFAULT_PITCH,
            FONT_FACE,
        )

    def _round_window(self, width: int, height: int) -> None:
        radius = self._mm_to_pixels(OVERLAY_RADIUS_MM)
        region = self.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
        self.user32.SetWindowRgn(self.hwnd, region, True)

    def _mm_to_pixels(self, value: float) -> int:
        dpi = 96
        if hasattr(self.user32, "GetDpiForWindow"):
            try:
                dpi = int(self.user32.GetDpiForWindow(self.hwnd))
            except OSError:
                dpi = 96
        return max(1, round(value * dpi / 25.4))


def _format_label(index: int, suggestion: Suggestion, focus_index: int = 0) -> str:
    return suggestion.replacement


def _measure_width(labels: list[str], appearance: AppearanceSettings) -> int:
    config = _size_config(appearance)
    return min(max(240, sum(_label_width(label, config) for label in labels) + 16), 900)


def _choice_bounds(labels: list[str], appearance: AppearanceSettings) -> list[tuple[int, int]]:
    config = _size_config(appearance)
    bounds: list[tuple[int, int]] = []
    x = 10
    for label in labels:
        width = _label_width(label, config)
        bounds.append((x, x + width))
        x += width
    return bounds


def choice_index_at_x(bounds: list[tuple[int, int]], x: int) -> int | None:
    for index, (left, right) in enumerate(bounds):
        if left <= x < right:
            return index
    return None


def _label_width(label: str, config: dict[str, int]) -> int:
    return max(config["min_choice_width"], len(label) * config["char_width"] + config["padding"])


def calculate_overlay_position(
    anchor_x: int,
    anchor_y: int,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    margin: int = 8,
) -> tuple[int, int]:
    pos_x = min(max(anchor_x + 10, margin), max(margin, screen_width - width - margin))
    below_y = anchor_y + 18
    above_y = anchor_y - height - 10
    if below_y + height + margin <= screen_height:
        pos_y = below_y
    else:
        pos_y = above_y
    pos_y = min(max(pos_y, margin), max(margin, screen_height - height - margin))
    return pos_x, pos_y


def _theme(appearance: AppearanceSettings) -> dict[str, int]:
    return THEMES.get(appearance.theme, THEMES["dark"])


def _size_config(appearance: AppearanceSettings) -> dict[str, int]:
    return SIZE_CONFIG.get(appearance.suggestion_size, SIZE_CONFIG["medium"])


def _is_windows_overlay_available() -> bool:
    return hasattr(ctypes, "windll") and WndProc is not None
