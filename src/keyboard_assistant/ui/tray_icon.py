from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes

from keyboard_assistant.ui.app_icon import destroy_app_icon, load_app_icon


WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_APP_TRAY = 0x8002
WS_OVERLAPPED = 0x00000000
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800

ID_TRAY_PAUSE = 401
ID_TRAY_SETTINGS = 402
ID_TRAY_EXIT = 403

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
UINT_PTR = getattr(wintypes, "UINT_PTR", ctypes.c_size_t)


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


    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", HICON),
            ("szTip", wintypes.WCHAR * 128),
        ]
else:
    WNDCLASS = None
    NOTIFYICONDATA = None


class TrayIcon:
    def __init__(
        self,
        on_toggle_pause: Callable[[], bool],
        on_open_settings: Callable[[], None],
        on_exit: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> None:
        if not _is_windows_tray_available():
            raise RuntimeError("Tray icon is currently Windows-only.")
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        self.kernel32 = ctypes.windll.kernel32
        self._configure_win32_api()
        self.on_toggle_pause = on_toggle_pause
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit
        self.is_paused = is_paused
        self._wnd_proc_ref = WndProc(self._wnd_proc)
        self._class_name = f"KeyboardAssistantTrayWindow{id(self)}"
        self._class_registered = False
        self._closed = False
        self._register_class()
        self.hwnd = self._create_window()
        self.icon, self._owns_icon = load_app_icon(self.user32, 16, 16)
        self._add_icon()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if getattr(self, "hwnd", None):
            data = self._notify_data()
            self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._class_registered:
            self.user32.UnregisterClassW(self._class_name, self.kernel32.GetModuleHandleW(None))
            self._class_registered = False
        destroy_app_icon(self.user32, getattr(self, "icon", 0), getattr(self, "_owns_icon", False))
        self.icon = 0
        self._owns_icon = False

    def update_tooltip(self) -> None:
        if getattr(self, "hwnd", None):
            data = self._notify_data()
            self.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def _register_class(self) -> None:
        if WNDCLASS is None:
            raise RuntimeError("Tray icon is currently Windows-only.")
        instance = self.kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASS()
        wndclass.lpfnWndProc = self._wnd_proc_ref
        wndclass.hInstance = instance
        wndclass.lpszClassName = self._class_name
        atom = self.user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            raise ctypes.WinError(self.kernel32.GetLastError())
        self._class_registered = True

    def _create_window(self) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            self._class_name,
            "Keyboard Assistant Tray",
            WS_OVERLAPPED,
            0,
            0,
            0,
            0,
            0,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _add_icon(self) -> None:
        data = self._notify_data()
        if not self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            raise ctypes.WinError()

    def _notify_data(self) -> NOTIFYICONDATA:
        if NOTIFYICONDATA is None:
            raise RuntimeError("Tray icon is currently Windows-only.")
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_APP_TRAY
        data.hIcon = self.icon
        status = "Paused" if self.is_paused() else "On"
        data.szTip = f"Keyboard Assistant - {status}"
        return data

    def _wnd_proc(self, hwnd: int, message: int, w_param: int, l_param: int) -> int:
        if message == WM_APP_TRAY:
            if l_param in {WM_RBUTTONUP, WM_LBUTTONDBLCLK}:
                self._show_menu()
            return 0
        if message == WM_COMMAND:
            self._handle_command(w_param & 0xFFFF)
            return 0
        if message == WM_DESTROY:
            return 0
        return self.user32.DefWindowProcW(hwnd, message, w_param, l_param)

    def _show_menu(self) -> None:
        menu = self.user32.CreatePopupMenu()
        if not menu:
            return
        pause_text = "Resume" if self.is_paused() else "Pause"
        self.user32.AppendMenuW(menu, MF_STRING, ID_TRAY_PAUSE, pause_text)
        self.user32.AppendMenuW(menu, MF_STRING, ID_TRAY_SETTINGS, "Settings")
        self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        self.user32.AppendMenuW(menu, MF_STRING, ID_TRAY_EXIT, "Exit")
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        self.user32.SetForegroundWindow(self.hwnd)
        command = self.user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        self.user32.DestroyMenu(menu)
        if command:
            self._handle_command(command)

    def _handle_command(self, command_id: int) -> None:
        if command_id == ID_TRAY_PAUSE:
            self.on_toggle_pause()
            self.update_tooltip()
        elif command_id == ID_TRAY_SETTINGS:
            self.on_open_settings()
        elif command_id == ID_TRAY_EXIT:
            self.on_exit()

    def _configure_win32_api(self) -> None:
        if WNDCLASS is None or NOTIFYICONDATA is None:
            raise RuntimeError("Tray icon is currently Windows-only.")
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
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]
        self.user32.CreatePopupMenu.restype = HMENU
        self.user32.AppendMenuW.argtypes = [HMENU, wintypes.UINT, UINT_PTR, wintypes.LPCWSTR]
        self.user32.TrackPopupMenu.argtypes = [
            HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        ]
        self.user32.TrackPopupMenu.restype = wintypes.UINT
        self.user32.DestroyMenu.argtypes = [HMENU]
        self.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
        self.shell32.Shell_NotifyIconW.restype = wintypes.BOOL


def _is_windows_tray_available() -> bool:
    return hasattr(ctypes, "windll") and WndProc is not None and WNDCLASS is not None and NOTIFYICONDATA is not None
