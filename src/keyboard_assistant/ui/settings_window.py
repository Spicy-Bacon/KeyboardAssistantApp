from __future__ import annotations

import ctypes
from ctypes import wintypes

from keyboard_assistant.storage.database import Database
from keyboard_assistant.ui.app_icon import destroy_app_icon, load_app_icon


WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_SETICON = 0x0080
WM_SETTEXT = 0x000C
WM_SETFONT = 0x0030
WM_CTLCOLORBTN = 0x0135
WM_CTLCOLOREDIT = 0x0133
WM_CTLCOLORLISTBOX = 0x0134
WM_CTLCOLORSTATIC = 0x0138
WM_LBUTTONDOWN = 0x0201
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
WS_TABSTOP = 0x00010000
BS_PUSHBUTTON = 0x00000000
BS_FLAT = 0x00008000
SS_LEFT = 0x00000000
SS_CENTER = 0x00000001
SS_CENTERIMAGE = 0x00000200
SS_NOTIFY = 0x00000100
ES_AUTOHSCROLL = 0x0080
LBS_NOTIFY = 0x0001
WS_VSCROLL = 0x00200000
CBS_DROPDOWNLIST = 0x0003
CB_ADDSTRING = 0x0143
CB_GETCURSEL = 0x0147
CB_SETCURSEL = 0x014E
LB_ADDSTRING = 0x0180
LB_RESETCONTENT = 0x0184
CW_USEDEFAULT = -2147483648
SW_HIDE = 0
SW_SHOW = 5
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
TRANSPARENT = 1
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
ICON_SMALL = 0
ICON_BIG = 1

DARK_BACKGROUND = 0x00202020
DARK_SIDEBAR = 0x001A1A1A
DARK_PANEL = 0x002A2A2A
DARK_INPUT = 0x00323232
DARK_ACTIVE = 0x003A3A3A
TEXT_PRIMARY = 0x00F2F2F2
TEXT_SECONDARY = 0x00B8B8B8
TEXT_ACCENT = 0x00D6D6D6
CONTROL_RADIUS_MM = 2.0
WINDOW_WIDTH = 980
WINDOW_HEIGHT = 820
SIDEBAR_X = 16
SIDEBAR_Y = 18
SIDEBAR_WIDTH = 170
MAIN_X = 214
MAIN_WIDTH = 720

ID_CLEAR_LEARNING = 104
ID_CLOSE = 105
ID_APP_OFF = 201
ID_APP_LIMITED = 202
ID_APP_ON = 203
ID_DICT_ADD = 301
ID_DICT_ADD_NEVER = 302
ID_DICT_REMOVE = 303
ID_THEME = 401
ID_SIZE = 402
ID_OPACITY = 403
ID_ANIMATIONS = 404
ID_AI_TOGGLE = 501
ID_AI_PROVIDER = 502
ID_AI_MODEL = 503
ID_ASSISTANT_COMBO = 601
ID_STRENGTH_COMBO = 602
ID_LEARNING_COMBO = 603
ID_THEME_COMBO = 604
ID_NAV_GENERAL = 701
ID_NAV_APPS = 702
ID_NAV_DICTIONARY = 703
ID_NAV_APPEARANCE = 704
ID_NAV_AI = 705

WndProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
) if hasattr(ctypes, "WINFUNCTYPE") else None

HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HDC = getattr(wintypes, "HDC", wintypes.HANDLE)
HFONT = getattr(wintypes, "HFONT", wintypes.HANDLE)
HGDIOBJ = getattr(wintypes, "HGDIOBJ", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HINSTANCE = getattr(wintypes, "HINSTANCE", wintypes.HANDLE)
HMENU = getattr(wintypes, "HMENU", wintypes.HANDLE)
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
else:
    WNDCLASS = None


class SettingsWindow:
    def __init__(self, database: Database) -> None:
        if not hasattr(ctypes, "windll") or WndProc is None or WNDCLASS is None:
            raise RuntimeError("Settings window is currently Windows-only.")
        self.database = database
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.kernel32 = ctypes.windll.kernel32
        self.dwmapi = getattr(ctypes.windll, "dwmapi", None)
        self.uxtheme = getattr(ctypes.windll, "uxtheme", None)
        self._configure_win32_api()
        self._brush_background = self.gdi32.CreateSolidBrush(DARK_BACKGROUND)
        self._brush_sidebar = self.gdi32.CreateSolidBrush(DARK_SIDEBAR)
        self._brush_panel = self.gdi32.CreateSolidBrush(DARK_PANEL)
        self._brush_input = self.gdi32.CreateSolidBrush(DARK_INPUT)
        self._brush_active = self.gdi32.CreateSolidBrush(DARK_ACTIVE)
        self._font = self._create_font(18, weight=400)
        self._title_font = self._create_font(28, weight=600)
        self._wnd_proc_ref = WndProc(self._wnd_proc)
        self._class_name = f"KeyboardAssistantSettingsWindow{id(self)}"
        self._class_registered = False
        self._initializing = True
        self._controls: dict[str, int] = {}
        self._control_roles: dict[int, str] = {}
        self._pages: dict[str, list[int]] = {"general": [], "apps": [], "dictionary": [], "appearance": [], "ai": []}
        self._active_page = "general"
        self._nav_pages: dict[int, str] = {}
        self._dropdowns: dict[str, dict[str, object]] = {}
        self._dropdown_option_actions: dict[int, tuple[str, int]] = {}
        self._next_dropdown_option_id = 900
        self._icon_big = 0
        self._icon_small = 0
        self._owns_icon_big = False
        self._owns_icon_small = False
        self._register_class()
        self.hwnd = self._create_window()
        self._icon_big, self._owns_icon_big = load_app_icon(self.user32, 32, 32)
        self._icon_small, self._owns_icon_small = load_app_icon(self.user32, 16, 16)
        self._apply_window_icons()
        self._apply_dark_title_bar()
        self._create_controls()
        self._initializing = False
        self.refresh()

    def run(self) -> None:
        self.user32.ShowWindow(self.hwnd, SW_SHOW)
        message = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(message), 0, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(message))
            self.user32.DispatchMessageW(ctypes.byref(message))

    def close(self) -> None:
        if getattr(self, "hwnd", None):
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._class_registered:
            self.user32.UnregisterClassW(self._class_name, self.kernel32.GetModuleHandleW(None))
            self._class_registered = False
        destroy_app_icon(self.user32, getattr(self, "_icon_big", 0), getattr(self, "_owns_icon_big", False))
        destroy_app_icon(self.user32, getattr(self, "_icon_small", 0), getattr(self, "_owns_icon_small", False))
        self._icon_big = 0
        self._icon_small = 0
        self._owns_icon_big = False
        self._owns_icon_small = False
        for handle in (
            getattr(self, "_font", None),
            getattr(self, "_title_font", None),
            getattr(self, "_brush_background", None),
            getattr(self, "_brush_sidebar", None),
            getattr(self, "_brush_panel", None),
            getattr(self, "_brush_input", None),
            getattr(self, "_brush_active", None),
        ):
            if handle:
                self.gdi32.DeleteObject(handle)

    def refresh(self) -> None:
        settings = self.database.get_settings()
        summary = self.database.data_summary()
        self._set_text(
            "data",
            "Local data: "
            f"{summary['personal_dictionary']} dictionary words, "
            f"{summary['accepted_suggestions']} accepted, "
            f"{summary['ignored_suggestions']} ignored, "
            f"{summary['reverted_corrections']} reverted",
        )
        self._set_combo_index("assistant_combo", 0 if settings.assistant_enabled else 1)
        strengths = ["light", "balanced", "aggressive"]
        self._set_combo_index(
            "strength_combo",
            strengths.index(settings.correction_strength) if settings.correction_strength in strengths else 1,
        )
        self._set_combo_index("learning_combo", 0 if settings.learning_enabled else 1)
        appearance = self.database.get_appearance_settings()
        themes = ["dark", "light", "system"]
        self._set_combo_index("theme_combo", themes.index(appearance.theme) if appearance.theme in themes else 0)
        self._set_text(
            "appearance_status",
            f"Size: {appearance.suggestion_size.title()} | "
            f"Opacity: {appearance.opacity}% | Animations: {'On' if appearance.animations_enabled else 'Off'}",
        )
        self._set_text("animations_button", "Animations Off" if appearance.animations_enabled else "Animations On")
        model_settings = self.database.get_model_settings()
        self._set_text(
            "ai_status",
            f"Status: {'On' if model_settings['enabled'] else 'Off'} | "
            f"Provider: {model_settings['provider']} | Model: {model_settings['model'] or '(none)'}",
        )
        self._set_text("ai_toggle", "AI Off" if model_settings["enabled"] else "AI On")

    def _register_class(self) -> None:
        if WNDCLASS is None:
            raise RuntimeError("Settings window is currently Windows-only.")
        instance = self.kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASS()
        wndclass.lpfnWndProc = self._wnd_proc_ref
        wndclass.hInstance = instance
        wndclass.lpszClassName = self._class_name
        wndclass.hbrBackground = self._brush_background
        atom = self.user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            raise ctypes.WinError(self.kernel32.GetLastError())
        self._class_registered = True

    def _create_window(self) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            self._class_name,
            "Keyboard Assistant Settings",
            WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            0,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _create_controls(self) -> None:
        self._controls["sidebar_panel"] = self._create_panel(SIDEBAR_X, SIDEBAR_Y, SIDEBAR_WIDTH, 744, "sidebar")
        self._controls["brand"] = self._create_static("Keyboard", 36, 36, 120, 26, title=True, role="sidebar")
        self._controls["brand_sub"] = self._create_static("Assistant", 38, 66, 118, 22, role="sidebar")
        self._create_sidebar_item("general", ID_NAV_GENERAL, "\uE713  General", 36, 126)
        self._create_sidebar_item("apps", ID_NAV_APPS, "\uE71D  Apps", 36, 172)
        self._create_sidebar_item("dictionary", ID_NAV_DICTIONARY, "\uE8D2  Dictionary", 36, 218)
        self._create_sidebar_item("appearance", ID_NAV_APPEARANCE, "\uE790  Appearance", 36, 264)
        self._create_sidebar_item("ai", ID_NAV_AI, "\uE950  Local AI", 36, 310)

        self._controls["title"] = self._create_static("Settings", MAIN_X, 26, 340, 34, title=True)
        self._controls["subtitle"] = self._create_static(
            "Local-first controls for suggestions, privacy, appearance, and AI.",
            MAIN_X + 2,
            64,
            MAIN_WIDTH,
            24,
        )

        self._controls["general_card"] = self._create_panel(MAIN_X, 104, MAIN_WIDTH, 356, "card", page="general")
        self._controls["assistant_label"] = self._create_static("Assistant", MAIN_X + 24, 132, 180, 22, role="card", page="general")
        self._controls["assistant_desc"] = self._create_static("Enable or pause live suggestions.", MAIN_X + 24, 156, 360, 22, role="card", page="general")
        self._controls["assistant_combo"] = self._create_combo("assistant_combo", ID_ASSISTANT_COMBO, MAIN_X + 536, 132, 150, page="general")
        self._combo_add_many("assistant_combo", ["On", "Off"])

        self._controls["strength_label"] = self._create_static("Correction strength", MAIN_X + 24, 206, 220, 22, role="card", page="general")
        self._controls["strength_desc"] = self._create_static("Controls how proactive automatic fixes can be.", MAIN_X + 24, 230, 400, 22, role="card", page="general")
        self._controls["strength_combo"] = self._create_combo("strength_combo", ID_STRENGTH_COMBO, MAIN_X + 516, 206, 170, page="general")
        self._combo_add_many("strength_combo", ["Light", "Balanced", "Aggressive"])

        self._controls["learning_label"] = self._create_static("Learning", MAIN_X + 24, 280, 180, 22, role="card", page="general")
        self._controls["learning_desc"] = self._create_static("Let the app adapt locally from accepted suggestions.", MAIN_X + 24, 304, 420, 22, role="card", page="general")
        self._controls["learning_combo"] = self._create_combo("learning_combo", ID_LEARNING_COMBO, MAIN_X + 536, 280, 150, page="general")
        self._combo_add_many("learning_combo", ["On", "Off"])
        self._controls["data"] = self._create_static("", MAIN_X + 24, 352, 470, 24, role="card", page="general")
        self._controls["clear_button"] = self._create_button("Clear learning", ID_CLEAR_LEARNING, MAIN_X + 548, 346, 138, 34, page="general")

        self._controls["apps_card"] = self._create_panel(MAIN_X, 104, MAIN_WIDTH, 430, "card", page="apps")
        self._controls["apps_title"] = self._create_static("Apps", MAIN_X + 24, 132, 220, 28, title=True, role="card", page="apps")
        self._controls["apps_desc"] = self._create_static("Set assistant behavior for specific applications.", MAIN_X + 24, 164, 440, 22, role="card", page="apps")
        self._controls["app_edit"] = self._create_edit("app.exe", MAIN_X + 24, 214, 260, 34, page="apps")
        self._controls["app_off"] = self._create_button("Off", ID_APP_OFF, MAIN_X + 304, 214, 82, 34, page="apps")
        self._controls["app_limited"] = self._create_button("Limited", ID_APP_LIMITED, MAIN_X + 398, 214, 104, 34, page="apps")
        self._controls["app_on"] = self._create_button("On", ID_APP_ON, MAIN_X + 514, 214, 82, 34, page="apps")
        self._controls["apps_list"] = self._create_listbox(MAIN_X + 24, 272, MAIN_WIDTH - 48, 220, page="apps")

        self._controls["dictionary_card"] = self._create_panel(MAIN_X, 104, MAIN_WIDTH, 430, "card", page="dictionary")
        self._controls["dictionary_title"] = self._create_static("Dictionary", MAIN_X + 24, 132, 260, 28, title=True, role="card", page="dictionary")
        self._controls["dictionary_desc"] = self._create_static("Add personal words or words that should never be corrected.", MAIN_X + 24, 164, 520, 22, role="card", page="dictionary")
        self._controls["dict_edit"] = self._create_edit("word", MAIN_X + 24, 214, 260, 34, page="dictionary")
        self._controls["dict_add"] = self._create_button("Add", ID_DICT_ADD, MAIN_X + 304, 214, 82, 34, page="dictionary")
        self._controls["dict_add_never"] = self._create_button("Never correct", ID_DICT_ADD_NEVER, MAIN_X + 398, 214, 136, 34, page="dictionary")
        self._controls["dict_remove"] = self._create_button("Remove", ID_DICT_REMOVE, MAIN_X + 546, 214, 104, 34, page="dictionary")
        self._controls["dict_list"] = self._create_listbox(MAIN_X + 24, 272, MAIN_WIDTH - 48, 220, page="dictionary")

        self._controls["appearance_card"] = self._create_panel(MAIN_X, 104, MAIN_WIDTH, 330, "card", page="appearance")
        self._controls["appearance_title"] = self._create_static("Appearance", MAIN_X + 24, 132, 260, 28, title=True, role="card", page="appearance")
        self._controls["appearance_desc"] = self._create_static("Adjust the suggestion overlay style and motion.", MAIN_X + 24, 164, 480, 22, role="card", page="appearance")
        self._controls["theme_label"] = self._create_static("Theme", MAIN_X + 24, 220, 180, 22, role="card", page="appearance")
        self._controls["theme_combo"] = self._create_combo("theme_combo", ID_THEME_COMBO, MAIN_X + 536, 216, 150, page="appearance")
        self._combo_add_many("theme_combo", ["Dark", "Light", "System"])
        self._controls["appearance_status"] = self._create_static("", MAIN_X + 24, 270, 520, 24, role="card", page="appearance")
        self._controls["size_button"] = self._create_button("Size", ID_SIZE, MAIN_X + 24, 322, 92, 34, page="appearance")
        self._controls["opacity_button"] = self._create_button("Opacity", ID_OPACITY, MAIN_X + 128, 322, 104, 34, page="appearance")
        self._controls["animations_button"] = self._create_button("", ID_ANIMATIONS, MAIN_X + 244, 322, 140, 34, page="appearance")

        self._controls["ai_card"] = self._create_panel(MAIN_X, 104, MAIN_WIDTH, 330, "card", page="ai")
        self._controls["ai_title"] = self._create_static("Local AI", MAIN_X + 24, 132, 260, 28, title=True, role="card", page="ai")
        self._controls["ai_desc"] = self._create_static("Optional local model suggestions. The built-in engine works without it.", MAIN_X + 24, 164, 560, 22, role="card", page="ai")
        self._controls["ai_status"] = self._create_static("", MAIN_X + 24, 218, 560, 24, role="card", page="ai")
        self._controls["ai_toggle"] = self._create_button("", ID_AI_TOGGLE, MAIN_X + 24, 276, 86, 34, page="ai")
        self._controls["ai_provider"] = self._create_button("Provider", ID_AI_PROVIDER, MAIN_X + 124, 276, 112, 34, page="ai")
        self._controls["ai_model_edit"] = self._create_edit("model", MAIN_X + 250, 276, 230, 34, page="ai")
        self._controls["ai_model"] = self._create_button("Save", ID_AI_MODEL, MAIN_X + 496, 276, 92, 34, page="ai")

        self._controls["close_button"] = self._create_button("Close", ID_CLOSE, MAIN_X, 734, 104, 32)
        self._refresh_lists()
        self._set_active_page("general")

    def _create_sidebar_item(self, page: str, control_id: int, text: str, x: int, y: int) -> None:
        self._nav_pages[control_id] = page
        self._controls[f"nav_{page}_active"] = self._create_panel(x - 10, y - 5, SIDEBAR_WIDTH - 32, 34, "active")
        self._controls[f"nav_{page}"] = self._create_static(
            text,
            x,
            y,
            SIDEBAR_WIDTH - 44,
            24,
            role="sidebar",
            control_id=control_id,
        )

    def _create_panel(self, x: int, y: int, width: int, height: int, role: str, page: str | None = None) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "STATIC",
            "",
            WS_VISIBLE | WS_CHILD | SS_LEFT,
            x,
            y,
            width,
            height,
            self.hwnd,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._control_roles[hwnd] = role
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        self._add_page_control(hwnd, page)
        return hwnd

    def _create_static(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
        title: bool = False,
        role: str = "text",
        control_id: int = 0,
        page: str | None = None,
    ) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "STATIC",
            text,
            WS_VISIBLE | WS_CHILD | SS_LEFT | (SS_NOTIFY if control_id else 0),
            x,
            y,
            width,
            height,
            self.hwnd,
            control_id,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._control_roles[hwnd] = role
        self._set_control_font(hwnd, title=title)
        self._add_page_control(hwnd, page)
        return hwnd

    def _create_button(
        self,
        text: str,
        control_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        page: str | None = None,
    ) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "STATIC",
            text,
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | SS_NOTIFY | SS_CENTER | SS_CENTERIMAGE,
            x,
            y,
            width,
            height,
            self.hwnd,
            control_id,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._set_control_font(hwnd)
        self._control_roles[hwnd] = "button"
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        self._add_page_control(hwnd, page)
        return hwnd

    def _create_edit(self, text: str, x: int, y: int, width: int, height: int, page: str | None = None) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "EDIT",
            text,
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | ES_AUTOHSCROLL,
            x,
            y,
            width,
            height,
            self.hwnd,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._set_control_font(hwnd)
        self._control_roles[hwnd] = "input"
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        self._add_page_control(hwnd, page)
        return hwnd

    def _create_listbox(self, x: int, y: int, width: int, height: int, page: str | None = None) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "LISTBOX",
            "",
            WS_VISIBLE | WS_CHILD | WS_BORDER | WS_VSCROLL | LBS_NOTIFY,
            x,
            y,
            width,
            height,
            self.hwnd,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._set_control_font(hwnd)
        self._control_roles[hwnd] = "input"
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        self._add_page_control(hwnd, page)
        return hwnd

    def _create_combo(self, name: str, control_id: int, x: int, y: int, width: int, page: str | None = None) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "STATIC",
            "",
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | SS_NOTIFY | SS_LEFT | SS_CENTERIMAGE,
            x,
            y,
            width,
            34,
            self.hwnd,
            control_id,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        self._set_control_font(hwnd)
        self._control_roles[hwnd] = "dropdown"
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, 34, CONTROL_RADIUS_MM)
        self._add_page_control(hwnd, page)
        self._dropdowns[name] = {
            "hwnd": hwnd,
            "control_id": control_id,
            "x": x,
            "y": y,
            "width": width,
            "page": page,
            "values": [],
            "index": 0,
            "options": [],
            "open": False,
        }
        return hwnd

    def _combo_add_many(self, name: str, values: list[str]) -> None:
        dropdown = self._dropdowns[name]
        dropdown["values"] = list(values)
        page = dropdown["page"]
        x = int(dropdown["x"])
        y = int(dropdown["y"])
        width = int(dropdown["width"])
        option_controls: list[int] = []
        for index, value in enumerate(values):
            option_id = self._next_dropdown_option_id
            self._next_dropdown_option_id += 1
            option = self._create_static(
                f"  {value}",
                x,
                y + 38 + index * 32,
                width,
                30,
                role="dropdown_option",
                control_id=option_id,
                page=page if isinstance(page, str) else None,
            )
            self._round_control(option, width, 30, CONTROL_RADIUS_MM)
            self.user32.ShowWindow(option, SW_HIDE)
            self._dropdown_option_actions[option_id] = (name, index)
            option_controls.append(option)
        dropdown["options"] = option_controls
        self._set_combo_index(name, 0)

    def _set_combo_index(self, name: str, index: int) -> None:
        dropdown = self._dropdowns[name]
        values = dropdown.get("values", [])
        if not values:
            dropdown["index"] = 0
            return
        safe_index = max(0, min(index, len(values) - 1))
        dropdown["index"] = safe_index
        self._set_text(name, f"  {values[safe_index]}  \u02c5")

    def _get_combo_index(self, name: str) -> int:
        return int(self._dropdowns[name].get("index", 0))

    def _add_page_control(self, hwnd: int, page: str | None) -> None:
        if page:
            self._pages.setdefault(page, []).append(hwnd)

    def _set_active_page(self, page: str) -> None:
        if page not in self._pages:
            return
        self._active_page = page
        self._hide_dropdowns()
        titles = {
            "general": "General",
            "apps": "Apps",
            "dictionary": "Dictionary",
            "appearance": "Appearance",
            "ai": "Local AI",
        }
        self._set_text("title", titles.get(page, "Settings"))
        for page_name, handles in self._pages.items():
            command = SW_SHOW if page_name == page else SW_HIDE
            for hwnd in handles:
                self.user32.ShowWindow(hwnd, command)
        self._hide_dropdowns()
        for page_name in self._pages:
            active_handle = self._controls.get(f"nav_{page_name}_active")
            label_handle = self._controls.get(f"nav_{page_name}")
            if active_handle:
                self.user32.ShowWindow(active_handle, SW_SHOW if page_name == page else SW_HIDE)
            if label_handle:
                self._control_roles[label_handle] = "active" if page_name == page else "sidebar"
                self.user32.InvalidateRect(label_handle, None, True)

    def _toggle_dropdown_by_control_id(self, control_id: int) -> bool:
        for name, dropdown in self._dropdowns.items():
            if dropdown.get("control_id") == control_id:
                if dropdown.get("open"):
                    self._hide_dropdowns()
                else:
                    self._show_dropdown(name)
                return True
        return False

    def _show_dropdown(self, name: str) -> None:
        self._hide_dropdowns()
        dropdown = self._dropdowns[name]
        dropdown["open"] = True
        for hwnd in dropdown.get("options", []):
            self.user32.SetWindowPos(
                hwnd,
                HWND_TOP,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )

    def _hide_dropdowns(self) -> None:
        for dropdown in self._dropdowns.values():
            dropdown["open"] = False
            for hwnd in dropdown.get("options", []):
                self.user32.ShowWindow(hwnd, SW_HIDE)

    def _select_dropdown_option(self, name: str, index: int) -> None:
        self._set_combo_index(name, index)
        self._hide_dropdowns()
        if name == "assistant_combo":
            self.database.set_bool_setting("assistant_enabled", index == 0)
        elif name == "strength_combo":
            strengths = ["light", "balanced", "aggressive"]
            if 0 <= index < len(strengths):
                self.database.set_setting("correction_strength", strengths[index])
        elif name == "learning_combo":
            self.database.set_bool_setting("learning_enabled", index == 0)
        elif name == "theme_combo":
            themes = ["dark", "light", "system"]
            if 0 <= index < len(themes):
                self.database.set_appearance_settings(theme=themes[index])
        self.refresh()

    def _set_control_font(self, hwnd: int, title: bool = False) -> None:
        self.user32.SendMessageW(hwnd, WM_SETFONT, self._title_font if title else self._font, ctypes.c_void_p(1))

    def _round_control(self, hwnd: int, width: int, height: int, radius_mm: float) -> None:
        radius = self._mm_to_pixels(radius_mm)
        region = self.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
        self.user32.SetWindowRgn(hwnd, region, True)

    def _apply_flat_theme(self, hwnd: int) -> None:
        if self.uxtheme is None:
            return
        try:
            self.uxtheme.SetWindowTheme(hwnd, "", "")
        except OSError:
            pass

    def _apply_window_icons(self) -> None:
        if self._icon_big:
            self.user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, ctypes.c_void_p(self._icon_big))
        if self._icon_small:
            self.user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, ctypes.c_void_p(self._icon_small))

    def _apply_dark_title_bar(self) -> None:
        if self.dwmapi is None:
            return
        enabled = ctypes.c_int(1)
        background = wintypes.DWORD(DARK_BACKGROUND)
        text = wintypes.DWORD(TEXT_PRIMARY)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            try:
                self.dwmapi.DwmSetWindowAttribute(
                    self.hwnd,
                    attribute,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
            except OSError:
                continue
            break
        for attribute, value in ((DWMWA_CAPTION_COLOR, background), (DWMWA_TEXT_COLOR, text)):
            try:
                self.dwmapi.DwmSetWindowAttribute(
                    self.hwnd,
                    attribute,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except OSError:
                pass

    def _mm_to_pixels(self, value: float) -> int:
        dpi = 96
        if hasattr(self.user32, "GetDpiForWindow"):
            try:
                dpi = int(self.user32.GetDpiForWindow(self.hwnd))
            except OSError:
                dpi = 96
        return max(1, round(value * dpi / 25.4))

    def _create_font(self, height: int, weight: int = 400) -> int:
        return self.gdi32.CreateFontW(
            -height,
            0,
            0,
            0,
            weight,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            "Segoe UI",
        )

    def _set_text(self, name: str, text: str) -> None:
        self.user32.SetWindowTextW(self._controls[name], text)

    def _get_text(self, name: str, max_chars: int = 256) -> str:
        buffer = ctypes.create_unicode_buffer(max_chars)
        self.user32.GetWindowTextW(self._controls[name], buffer, max_chars)
        return buffer.value.strip()

    def _refresh_lists(self) -> None:
        app_list = self._controls.get("apps_list")
        if app_list:
            self.user32.SendMessageW(app_list, LB_RESETCONTENT, 0, None)
            for profile in self.database.list_app_profiles():
                text = (
                    f"{profile.app_identifier} | {profile.assistant_status} | "
                    f"{profile.correction_strength} | learning={'on' if profile.learning_enabled else 'off'}"
                )
                self._listbox_add(app_list, text)

        dict_list = self._controls.get("dict_list")
        if dict_list:
            self.user32.SendMessageW(dict_list, LB_RESETCONTENT, 0, None)
            for word in self.database.list_personal_words():
                never = " | never correct" if word["never_correct"] else ""
                self._listbox_add(dict_list, f"{word['word']}{never}")

    def _listbox_add(self, hwnd: int, text: str) -> None:
        value = ctypes.c_wchar_p(text)
        self.user32.SendMessageW(hwnd, LB_ADDSTRING, 0, value)

    def _wnd_proc(self, hwnd: int, message: int, w_param: int, l_param: int) -> int:
        if message == WM_COMMAND:
            if not self._initializing:
                self._handle_command(w_param & 0xFFFF)
            return 0
        if message in {WM_CTLCOLORSTATIC, WM_CTLCOLOREDIT, WM_CTLCOLORLISTBOX, WM_CTLCOLORBTN}:
            return self._handle_control_color(message, w_param, l_param)
        if message == WM_DESTROY:
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, message, w_param, l_param)

    def _handle_control_color(self, message: int, device_context: int, control_hwnd: int) -> int:
        self.gdi32.SetTextColor(device_context, TEXT_PRIMARY)
        self.gdi32.SetBkMode(device_context, TRANSPARENT)
        role = self._control_roles.get(int(control_hwnd), "text")
        if message in {WM_CTLCOLOREDIT, WM_CTLCOLORLISTBOX}:
            self.gdi32.SetBkColor(device_context, DARK_INPUT)
            return self._brush_input
        if role == "sidebar":
            self.gdi32.SetBkColor(device_context, DARK_SIDEBAR)
            return self._brush_sidebar
        if role == "active":
            self.gdi32.SetBkColor(device_context, DARK_ACTIVE)
            return self._brush_active
        if role in {"button", "dropdown", "dropdown_option"}:
            self.gdi32.SetBkColor(device_context, DARK_INPUT if role == "dropdown" else DARK_ACTIVE)
            return self._brush_input if role == "dropdown" else self._brush_active
        if role == "card":
            self.gdi32.SetBkColor(device_context, DARK_PANEL)
            return self._brush_panel
        if message == WM_CTLCOLORBTN:
            self.gdi32.SetBkColor(device_context, DARK_PANEL)
            return self._brush_panel
        self.gdi32.SetBkColor(device_context, DARK_BACKGROUND)
        return self._brush_background

    def _handle_command(self, control_id: int) -> None:
        if control_id in self._nav_pages:
            self._set_active_page(self._nav_pages[control_id])
            return
        if control_id in self._dropdown_option_actions:
            name, index = self._dropdown_option_actions[control_id]
            self._select_dropdown_option(name, index)
            return
        if self._toggle_dropdown_by_control_id(control_id):
            return
        self._hide_dropdowns()

        if control_id == ID_CLEAR_LEARNING:
            self.database.clear_learning_data()
        elif control_id in {ID_APP_OFF, ID_APP_LIMITED, ID_APP_ON}:
            identifier = self._get_text("app_edit")
            if identifier:
                status = {ID_APP_OFF: "off", ID_APP_LIMITED: "limited", ID_APP_ON: "on"}[control_id]
                self.database.upsert_app_profile(identifier, assistant_status=status)
        elif control_id == ID_DICT_ADD:
            word = self._get_text("dict_edit")
            if word:
                self.database.add_personal_word(word)
        elif control_id == ID_DICT_ADD_NEVER:
            word = self._get_text("dict_edit")
            if word:
                self.database.add_personal_word(word, never_correct=True)
        elif control_id == ID_DICT_REMOVE:
            word = self._get_text("dict_edit")
            if word:
                self.database.remove_personal_word(word)
        elif control_id == ID_THEME:
            appearance = self.database.get_appearance_settings()
            themes = ["dark", "light", "system"]
            index = themes.index(appearance.theme) if appearance.theme in themes else 0
            self.database.set_appearance_settings(theme=themes[(index + 1) % len(themes)])
        elif control_id == ID_SIZE:
            appearance = self.database.get_appearance_settings()
            sizes = ["small", "medium", "large"]
            index = sizes.index(appearance.suggestion_size) if appearance.suggestion_size in sizes else 1
            self.database.set_appearance_settings(suggestion_size=sizes[(index + 1) % len(sizes)])
        elif control_id == ID_OPACITY:
            appearance = self.database.get_appearance_settings()
            opacities = [70, 85, 94, 100]
            current = min(opacities, key=lambda item: abs(item - appearance.opacity))
            index = opacities.index(current)
            self.database.set_appearance_settings(opacity=opacities[(index + 1) % len(opacities)])
        elif control_id == ID_ANIMATIONS:
            appearance = self.database.get_appearance_settings()
            self.database.set_appearance_settings(animations_enabled=not appearance.animations_enabled)
        elif control_id == ID_AI_TOGGLE:
            model_settings = self.database.get_model_settings()
            self.database.set_model_settings(enabled=not bool(model_settings["enabled"]))
        elif control_id == ID_AI_PROVIDER:
            model_settings = self.database.get_model_settings()
            provider = "ollama" if model_settings["provider"] == "none" else "none"
            enabled = provider != "none" and bool(model_settings["enabled"])
            self.database.set_model_settings(provider=provider, enabled=enabled)
        elif control_id == ID_AI_MODEL:
            model = self._get_text("ai_model_edit")
            self.database.set_model_settings(model="" if model == "model" else model)
        elif control_id == ID_CLOSE:
            self.close()
            return
        self.refresh()
        self._refresh_lists()

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
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_void_p]
        self.user32.SendMessageW.restype = wintypes.LPARAM
        self.user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
        self.user32.InvalidateRect.restype = wintypes.BOOL
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.SetWindowRgn.argtypes = [wintypes.HWND, HRGN, wintypes.BOOL]
        self.user32.SetWindowRgn.restype = ctypes.c_int
        if hasattr(self.user32, "GetDpiForWindow"):
            self.user32.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user32.GetDpiForWindow.restype = wintypes.UINT
        self.user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]
        self.gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
        self.gdi32.CreateSolidBrush.restype = HBRUSH
        self.gdi32.CreateRoundRectRgn.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.gdi32.CreateRoundRectRgn.restype = HRGN
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
        self.gdi32.SetTextColor.argtypes = [HDC, wintypes.COLORREF]
        self.gdi32.SetTextColor.restype = wintypes.COLORREF
        self.gdi32.SetBkColor.argtypes = [HDC, wintypes.COLORREF]
        self.gdi32.SetBkColor.restype = wintypes.COLORREF
        self.gdi32.SetBkMode.argtypes = [HDC, ctypes.c_int]
        self.gdi32.SetBkMode.restype = ctypes.c_int
        self.gdi32.DeleteObject.argtypes = [HGDIOBJ]
        self.gdi32.DeleteObject.restype = wintypes.BOOL
        if self.dwmapi is not None:
            self.dwmapi.DwmSetWindowAttribute.argtypes = [
                wintypes.HWND,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self.dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        if self.uxtheme is not None:
            self.uxtheme.SetWindowTheme.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
            self.uxtheme.SetWindowTheme.restype = ctypes.c_long
