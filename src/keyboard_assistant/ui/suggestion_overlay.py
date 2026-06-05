from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import queue
import time

from keyboard_assistant.core.models import Suggestion
from keyboard_assistant.core.models import AppearanceSettings


WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_LBUTTONDOWN = 0x0201
WM_MOUSEMOVE = 0x0200
WM_SETCURSOR = 0x0020
WM_NCLBUTTONDOWN = 0x00A1
WM_TIMER = 0x0113
WM_APP_DRAIN_QUEUE = 0x8001
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
LWA_ALPHA = 0x00000002
SRCCOPY = 0x00CC0020
DT_LEFT = 0x00000000
DT_CENTER = 0x00000001
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
NULL_PEN = 8
HTCAPTION = 2
IDC_HAND = 32649
IDC_SIZEALL = 32646
DEFAULT_CHARSET = 1
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
CLEARTYPE_QUALITY = 5
DEFAULT_PITCH = 0
FW_NORMAL = 400
FONT_FACE = "Segoe UI"
MONITOR_DEFAULTTONEAREST = 2
ANIMATION_TIMER_ID = 41
ANIMATION_TIMER_MS = 16
TRANSITION_DURATION_MS = 150
WINDOW_MOVE_JITTER_PX = 2
THEMES = {
    "dark": {
        "text_primary": 0x00F2F2F2,
        "text_secondary": 0x00B8B8B8,
        "background": 0x00212121,
        "highlight_background": 0x00363636,
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
        "background": 0x00212121,
        "highlight_background": 0x00363636,
    },
}
OVERLAY_RADIUS_MM = 1.5
CHIP_RADIUS_MM = 1.5
DRAG_HANDLE_WIDTH = 24
DRAG_HANDLE_GAP = 6
DOT_SIZE = 2
DOT_GAP = 3
OVERLAY_PADDING_X = 10
CHIP_VERTICAL_MARGIN = 5
CHIP_GAP = 6
SIZE_CONFIG = {
    "small": {"height": 32, "font_height": -13, "char_width": 7, "padding": 22, "min_choice_width": 92},
    "medium": {"height": 38, "font_height": -15, "char_width": 8, "padding": 26, "min_choice_width": 118},
    "large": {"height": 46, "font_height": -17, "char_width": 10, "padding": 30, "min_choice_width": 144},
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
HBITMAP = getattr(wintypes, "HBITMAP", wintypes.HANDLE)
HMONITOR = getattr(wintypes, "HMONITOR", wintypes.HANDLE)
UINT_PTR = getattr(wintypes, "UINT_PTR", ctypes.c_size_t)


@dataclass(frozen=True)
class ScreenBounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


@dataclass(frozen=True)
class OverlayLayout:
    labels: tuple[str, ...]
    focus_index: int
    width: int
    height: int
    chip_rects: tuple[tuple[int, int, int, int], ...]
    text_rects: tuple[tuple[int, int, int, int], ...]

    @property
    def choice_bounds(self) -> list[tuple[int, int]]:
        return [(left, right) for left, _top, right, _bottom in self.chip_rects]


@dataclass
class OverlayTransition:
    duration_ms: int = TRANSITION_DURATION_MS
    started_at: float | None = None

    def start(self, now: float | None = None) -> None:
        self.started_at = now if now is not None else time.monotonic()

    def stop(self) -> None:
        self.started_at = None

    def is_active(self, now: float | None = None) -> bool:
        return self.progress(now) < 1.0

    def progress(self, now: float | None = None) -> float:
        if self.started_at is None:
            return 1.0
        current = now if now is not None else time.monotonic()
        elapsed_ms = max(0.0, (current - self.started_at) * 1000.0)
        return min(1.0, elapsed_ms / max(1, self.duration_ms))

    def slide_offset(self, height: int, now: float | None = None) -> int:
        progress = _ease_out_cubic(self.progress(now))
        return round((1.0 - progress) * max(3, height * 0.12))

    def alpha_factor(self, now: float | None = None) -> float:
        progress = _ease_out_cubic(self.progress(now))
        return 0.9 + 0.1 * progress


class OverlayRenderState:
    def __init__(self, appearance: AppearanceSettings | None = None) -> None:
        self.appearance = appearance or AppearanceSettings()
        self.layout = build_overlay_layout([], self.appearance)
        self.transition = OverlayTransition()
        self.visible = False

    def update(
        self,
        suggestions: list[Suggestion],
        appearance: AppearanceSettings,
        focus_index: int = 0,
        now: float | None = None,
    ) -> OverlayLayout:
        labels = tuple(_format_label(index, suggestion, focus_index) for index, suggestion in enumerate(suggestions[:3]))
        focus = max(0, min(focus_index, max(0, len(labels) - 1)))
        previous_labels = self.layout.labels
        self.appearance = appearance
        self.layout = build_overlay_layout(labels, appearance, focus)
        if not labels:
            self.visible = False
            self.transition.stop()
            return self.layout
        if self.visible and labels != previous_labels and appearance.animations_enabled:
            self.transition.start(now)
        elif not self.visible:
            self.transition.stop()
        self.visible = True
        return self.layout

    def hide(self) -> None:
        self.visible = False
        self.layout = build_overlay_layout([], self.appearance)
        self.transition.stop()


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


    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]
else:
    WNDCLASS = None
    PAINTSTRUCT = None
    MONITORINFO = None


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
        self._cursor_drag = self.user32.LoadCursorW(None, ctypes.c_void_p(IDC_SIZEALL))
        self._cursor_hand = self.user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND))
        self.on_close = on_close
        self.on_select = on_select
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._render_state = OverlayRenderState()
        self._layout = self._render_state.layout
        self._choice_bounds: list[tuple[int, int]] = []
        self._appearance = AppearanceSettings()
        self._target_alpha = int(self._appearance.opacity * 255 / 100)
        self._last_window_rect: tuple[int, int, int, int] | None = None
        self._visible = False
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
            self._stop_animation_timer()
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
        layout = self._render_state.update(suggestions, self._appearance, focus_index)
        self._layout = layout
        self._choice_bounds = layout.choice_bounds
        if not layout.labels:
            self.hide()
            return
        bounds = self._screen_bounds_for_anchor(x, y)
        pos_x, pos_y = calculate_overlay_position(
            x,
            y,
            layout.width,
            layout.height,
            bounds.width,
            bounds.height,
            screen_left=bounds.left,
            screen_top=bounds.top,
        )
        self._move_or_resize_window(pos_x, pos_y, layout.width, layout.height)
        self._round_window(layout.width, layout.height)
        self.user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        self._visible = True
        self._apply_alpha()
        self._invalidate(erase=False)
        self._start_animation_timer_if_needed()

    def apply_appearance(self, appearance: AppearanceSettings) -> None:
        self._appearance = appearance
        if getattr(self, "hwnd", None):
            alpha = max(30, min(100, appearance.opacity))
            self._target_alpha = int(alpha * 255 / 100)
            self._apply_alpha()
            self._invalidate(erase=False)

    def hide(self) -> None:
        if getattr(self, "hwnd", None):
            self._render_state.hide()
            self._layout = self._render_state.layout
            self._choice_bounds = []
            self._visible = False
            self._stop_animation_timer()
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
        self.user32.SetTimer.argtypes = [wintypes.HWND, UINT_PTR, wintypes.UINT, wintypes.LPVOID]
        self.user32.SetTimer.restype = UINT_PTR
        self.user32.KillTimer.argtypes = [wintypes.HWND, UINT_PTR]
        self.user32.KillTimer.restype = wintypes.BOOL
        self.user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.SendMessageW.restype = wintypes.LPARAM
        self.user32.ReleaseCapture.argtypes = []
        self.user32.ReleaseCapture.restype = wintypes.BOOL
        self.user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
        self.user32.LoadCursorW.restype = HCURSOR
        self.user32.SetCursor.argtypes = [HCURSOR]
        self.user32.SetCursor.restype = HCURSOR
        self.user32.SetWindowRgn.argtypes = [wintypes.HWND, HRGN, wintypes.BOOL]
        self.user32.SetWindowRgn.restype = ctypes.c_int
        self.user32.MoveWindow.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.BOOL,
        ]
        self.user32.MoveWindow.restype = wintypes.BOOL
        self.user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT), wintypes.BOOL]
        self.user32.InvalidateRect.restype = wintypes.BOOL
        self.user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetClientRect.restype = wintypes.BOOL
        self.user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), HBRUSH]
        self.user32.FillRect.restype = ctypes.c_int
        self.user32.DrawTextW.argtypes = [
            wintypes.HDC,
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.POINTER(wintypes.RECT),
            wintypes.UINT,
        ]
        self.user32.DrawTextW.restype = ctypes.c_int
        self.user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        self.user32.BeginPaint.restype = wintypes.HDC
        self.user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        self.user32.EndPaint.restype = wintypes.BOOL
        if hasattr(self.user32, "GetDpiForWindow"):
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user32.GetDpiForWindow.restype = wintypes.UINT
        if hasattr(self.user32, "MonitorFromPoint") and MONITORINFO is not None:
            self.user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            self.user32.MonitorFromPoint.restype = HMONITOR
            self.user32.GetMonitorInfoW.argtypes = [HMONITOR, ctypes.POINTER(MONITORINFO)]
            self.user32.GetMonitorInfoW.restype = wintypes.BOOL
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
        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        self.gdi32.CreateCompatibleBitmap.restype = HBITMAP
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self.gdi32.DeleteDC.restype = wintypes.BOOL
        self.gdi32.BitBlt.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
        ]
        self.gdi32.BitBlt.restype = wintypes.BOOL
        self.gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
        self.gdi32.SetBkMode.restype = ctypes.c_int
        self.gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
        self.gdi32.SetTextColor.restype = wintypes.COLORREF
        self.gdi32.DeleteObject.argtypes = [HGDIOBJ]
        self.gdi32.DeleteObject.restype = wintypes.BOOL
        self.gdi32.GetStockObject.argtypes = [ctypes.c_int]
        self.gdi32.GetStockObject.restype = HGDIOBJ
        self.gdi32.RoundRect.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.gdi32.RoundRect.restype = wintypes.BOOL

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
        if message == WM_TIMER and w_param == ANIMATION_TIMER_ID:
            self._on_animation_tick()
            return 0
        if message == WM_PAINT:
            self._paint(hwnd)
            return 0
        if message == WM_MOUSEMOVE:
            self._set_overlay_cursor(l_param & 0xFFFF)
            return 0
        if message == WM_SETCURSOR:
            self._set_overlay_cursor(0)
            return 1
        if message == WM_LBUTTONDOWN:
            x = l_param & 0xFFFF
            if is_drag_handle_x(x):
                self.user32.ReleaseCapture()
                self.user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
                return 0
            index = choice_index_at_x(self._choice_bounds, x)
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
            width = max(1, rect.right - rect.left)
            height = max(1, rect.bottom - rect.top)
            memory_dc = self.gdi32.CreateCompatibleDC(hdc)
            bitmap = self.gdi32.CreateCompatibleBitmap(hdc, width, height)
            previous_bitmap = self.gdi32.SelectObject(memory_dc, bitmap)
            try:
                self._paint_content(memory_dc, rect)
                self.gdi32.BitBlt(hdc, 0, 0, width, height, memory_dc, 0, 0, SRCCOPY)
            finally:
                if previous_bitmap:
                    self.gdi32.SelectObject(memory_dc, previous_bitmap)
                if bitmap:
                    self.gdi32.DeleteObject(bitmap)
                if memory_dc:
                    self.gdi32.DeleteDC(memory_dc)
        finally:
            self.user32.EndPaint(hwnd, ctypes.byref(paint))

    def _paint_content(self, hdc: int, rect: wintypes.RECT) -> None:
        theme = _theme(self._appearance)
        config = _size_config(self._appearance)
        brush = self.gdi32.CreateSolidBrush(theme["background"])
        self.user32.FillRect(hdc, ctypes.byref(rect), brush)
        self.gdi32.DeleteObject(brush)
        if not self._render_state.visible:
            return
        self._paint_drag_handle(hdc, theme, config)
        self.gdi32.SetBkMode(hdc, 1)
        font = self._create_text_font(config)
        previous_font = self.gdi32.SelectObject(hdc, font) if font else None
        previous_pen = self.gdi32.SelectObject(hdc, self.gdi32.GetStockObject(NULL_PEN))
        try:
            slide = self._render_state.transition.slide_offset(config["height"]) if self._appearance.animations_enabled else 0
            slide = min(slide, max(0, CHIP_VERTICAL_MARGIN - 2))
            for index, label in enumerate(self._layout.labels):
                if index >= len(self._layout.chip_rects):
                    continue
                left, top, right, bottom = self._layout.chip_rects[index]
                label_rect = wintypes.RECT(left, top + slide, right, bottom + slide)
                if index == self._layout.focus_index:
                    highlight = self.gdi32.CreateSolidBrush(theme["highlight_background"])
                    previous_brush = self.gdi32.SelectObject(hdc, highlight)
                    radius = self._mm_to_pixels(CHIP_RADIUS_MM) * 2
                    self.gdi32.RoundRect(
                        hdc,
                        label_rect.left,
                        label_rect.top,
                        label_rect.right,
                        label_rect.bottom,
                        radius,
                        radius,
                    )
                    if previous_brush:
                        self.gdi32.SelectObject(hdc, previous_brush)
                    self.gdi32.DeleteObject(highlight)
                self.gdi32.SetTextColor(
                    hdc,
                    theme["text_primary"] if index == self._layout.focus_index else theme["text_secondary"],
                )
                self.user32.DrawTextW(
                    hdc,
                    label,
                    -1,
                    ctypes.byref(label_rect),
                    DT_CENTER | DT_VCENTER | DT_SINGLELINE,
                )
        finally:
            if previous_pen:
                self.gdi32.SelectObject(hdc, previous_pen)
            if previous_font:
                self.gdi32.SelectObject(hdc, previous_font)
            if font:
                self.gdi32.DeleteObject(font)

    def _move_or_resize_window(self, x: int, y: int, width: int, height: int) -> None:
        next_rect = (x, y, width, height)
        previous = self._last_window_rect
        if previous:
            prev_x, prev_y, prev_width, prev_height = previous
            same_size = prev_width == width and prev_height == height
            tiny_move = abs(prev_x - x) <= WINDOW_MOVE_JITTER_PX and abs(prev_y - y) <= WINDOW_MOVE_JITTER_PX
            if same_size and tiny_move:
                return
        self.user32.MoveWindow(self.hwnd, x, y, width, height, False)
        self._last_window_rect = next_rect

    def _invalidate(self, erase: bool = False) -> None:
        if getattr(self, "hwnd", None):
            self.user32.InvalidateRect(self.hwnd, None, bool(erase))

    def _apply_alpha(self) -> None:
        factor = self._render_state.transition.alpha_factor() if self._appearance.animations_enabled else 1.0
        alpha = max(1, min(255, round(self._target_alpha * factor)))
        self.user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha, LWA_ALPHA)

    def _start_animation_timer_if_needed(self) -> None:
        if not self._appearance.animations_enabled:
            return
        if self._render_state.transition.is_active():
            self.user32.SetTimer(self.hwnd, ANIMATION_TIMER_ID, ANIMATION_TIMER_MS, None)

    def _stop_animation_timer(self) -> None:
        if getattr(self, "hwnd", None):
            self.user32.KillTimer(self.hwnd, ANIMATION_TIMER_ID)

    def _on_animation_tick(self) -> None:
        if not self._render_state.transition.is_active():
            self._render_state.transition.stop()
            self._apply_alpha()
            self._stop_animation_timer()
            self._invalidate(erase=False)
            return
        self._apply_alpha()
        self._invalidate(erase=False)

    def _screen_bounds_for_anchor(self, x: int, y: int) -> ScreenBounds:
        if hasattr(self.user32, "MonitorFromPoint") and MONITORINFO is not None:
            try:
                point = wintypes.POINT(x, y)
                monitor = self.user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
                if monitor:
                    info = MONITORINFO()
                    info.cbSize = ctypes.sizeof(MONITORINFO)
                    if self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                        return ScreenBounds(info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
            except OSError:
                pass
        return ScreenBounds(0, 0, self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1))

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

    def _paint_drag_handle(self, hdc: int, theme: dict[str, int], config: dict[str, int]) -> None:
        brush = self.gdi32.CreateSolidBrush(theme["text_secondary"])
        start_x = 8
        start_y = max(6, (config["height"] - (3 * DOT_SIZE + 2 * DOT_GAP)) // 2)
        try:
            for row in range(3):
                for column in range(2):
                    left = start_x + column * (DOT_SIZE + DOT_GAP)
                    top = start_y + row * (DOT_SIZE + DOT_GAP)
                    dot = wintypes.RECT(left, top, left + DOT_SIZE, top + DOT_SIZE)
                    self.user32.FillRect(hdc, ctypes.byref(dot), brush)
        finally:
            self.gdi32.DeleteObject(brush)

    def _set_overlay_cursor(self, x: int) -> None:
        cursor = self._cursor_drag if is_drag_handle_x(x) else self._cursor_hand
        if cursor:
            self.user32.SetCursor(cursor)

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


def build_overlay_layout(
    labels: list[str] | tuple[str, ...],
    appearance: AppearanceSettings,
    focus_index: int = 0,
) -> OverlayLayout:
    label_tuple = tuple(labels[:3])
    focus = max(0, min(focus_index, max(0, len(label_tuple) - 1)))
    rects = tuple(chip_rects(list(label_tuple), appearance))
    width = _measure_width(list(label_tuple), appearance)
    height = _size_config(appearance)["height"] if label_tuple else 0
    return OverlayLayout(
        labels=label_tuple,
        focus_index=focus,
        width=width,
        height=height,
        chip_rects=rects,
        text_rects=tuple(_text_rect(rect) for rect in rects),
    )


def _measure_width(labels: list[str], appearance: AppearanceSettings) -> int:
    if not labels:
        return 0
    rects = chip_rects(labels, appearance)
    return min(max(240, rects[-1][2] + OVERLAY_PADDING_X), 900)


def _choice_bounds(labels: list[str], appearance: AppearanceSettings) -> list[tuple[int, int]]:
    return [(left, right) for left, _top, right, _bottom in chip_rects(labels, appearance)]


def chip_rects(labels: list[str], appearance: AppearanceSettings) -> list[tuple[int, int, int, int]]:
    config = _size_config(appearance)
    if not labels:
        return []
    slot_width = max(config["min_choice_width"], max(_label_width(label, config) for label in labels))
    top = CHIP_VERTICAL_MARGIN
    bottom = config["height"] - CHIP_VERTICAL_MARGIN
    rects: list[tuple[int, int, int, int]] = []
    x = OVERLAY_PADDING_X + DRAG_HANDLE_WIDTH + DRAG_HANDLE_GAP
    for label in labels:
        rects.append((x, top, x + slot_width, bottom))
        x += slot_width + CHIP_GAP
    return rects


def choice_index_at_x(bounds: list[tuple[int, int]], x: int) -> int | None:
    for index, (left, right) in enumerate(bounds):
        if left <= x < right:
            return index
    return None


def is_drag_handle_x(x: int) -> bool:
    return 0 <= x < DRAG_HANDLE_WIDTH


def _label_width(label: str, config: dict[str, int]) -> int:
    return max(config["min_choice_width"], len(label) * config["char_width"] + config["padding"])


def _text_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return rect


def rect_center(rect: tuple[int, int, int, int]) -> tuple[float, float]:
    left, top, right, bottom = rect
    return ((left + right) / 2, (top + bottom) / 2)


def _ease_out_cubic(progress: float) -> float:
    clamped = max(0.0, min(1.0, progress))
    return 1 - pow(1 - clamped, 3)


def calculate_overlay_position(
    anchor_x: int,
    anchor_y: int,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
    margin: int = 8,
    screen_left: int = 0,
    screen_top: int = 0,
) -> tuple[int, int]:
    screen_right = screen_left + screen_width
    screen_bottom = screen_top + screen_height
    left_limit = screen_left + margin
    right_limit = max(left_limit, screen_right - width - margin)
    top_limit = screen_top + margin
    bottom_limit = max(top_limit, screen_bottom - height - margin)

    pos_x = min(max(anchor_x + 10, left_limit), right_limit)
    below_y = anchor_y + 18
    above_y = anchor_y - height - 10
    if below_y + height + margin <= screen_bottom:
        pos_y = below_y
    else:
        pos_y = above_y
    pos_y = min(max(pos_y, top_limit), bottom_limit)
    return pos_x, pos_y


def _theme(appearance: AppearanceSettings) -> dict[str, int]:
    return THEMES.get(appearance.theme, THEMES["dark"])


def _size_config(appearance: AppearanceSettings) -> dict[str, int]:
    return SIZE_CONFIG.get(appearance.suggestion_size, SIZE_CONFIG["medium"])


def _is_windows_overlay_available() -> bool:
    return hasattr(ctypes, "windll") and WndProc is not None
