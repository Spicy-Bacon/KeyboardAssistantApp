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
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
WS_TABSTOP = 0x00010000
BS_PUSHBUTTON = 0x00000000
BS_FLAT = 0x00008000
SS_LEFT = 0x00000000
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
SW_SHOW = 5
TRANSPARENT = 1
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
ICON_SMALL = 0
ICON_BIG = 1

DARK_BACKGROUND = 0x00202020
DARK_PANEL = 0x002A2A2A
DARK_INPUT = 0x00323232
TEXT_PRIMARY = 0x00F2F2F2
TEXT_SECONDARY = 0x00B8B8B8
CONTROL_RADIUS_MM = 2.0

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
        self._brush_panel = self.gdi32.CreateSolidBrush(DARK_PANEL)
        self._brush_input = self.gdi32.CreateSolidBrush(DARK_INPUT)
        self._font = self._create_font(18, weight=400)
        self._title_font = self._create_font(28, weight=600)
        self._wnd_proc_ref = WndProc(self._wnd_proc)
        self._class_name = f"KeyboardAssistantSettingsWindow{id(self)}"
        self._class_registered = False
        self._initializing = True
        self._controls: dict[str, int] = {}
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
            getattr(self, "_brush_panel", None),
            getattr(self, "_brush_input", None),
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
            760,
            820,
            0,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _create_controls(self) -> None:
        self._controls["title"] = self._create_static("Keyboard Assistant", 28, 24, 340, 34, title=True)
        self._controls["subtitle"] = self._create_static("Settings are saved locally and used the next time the desktop assistant starts.", 30, 62, 660, 24)

        self._controls["assistant_label"] = self._create_static("Assistant", 32, 108, 144, 22)
        self._controls["assistant_combo"] = self._create_combo(ID_ASSISTANT_COMBO, 32, 132, 150, 120)
        self._combo_add_many("assistant_combo", ["On", "Off"])

        self._controls["strength_label"] = self._create_static("Correction strength", 202, 108, 170, 22)
        self._controls["strength_combo"] = self._create_combo(ID_STRENGTH_COMBO, 202, 132, 170, 120)
        self._combo_add_many("strength_combo", ["Light", "Balanced", "Aggressive"])

        self._controls["learning_label"] = self._create_static("Learning", 392, 108, 144, 22)
        self._controls["learning_combo"] = self._create_combo(ID_LEARNING_COMBO, 392, 132, 150, 120)
        self._combo_add_many("learning_combo", ["On", "Off"])

        self._controls["theme_label"] = self._create_static("Theme", 562, 108, 144, 22)
        self._controls["theme_combo"] = self._create_combo(ID_THEME_COMBO, 562, 132, 150, 120)
        self._combo_add_many("theme_combo", ["Dark", "Light", "System"])

        self._controls["data"] = self._create_static("", 32, 178, 660, 24)
        self._controls["clear_button"] = self._create_button("Clear learning", ID_CLEAR_LEARNING, 32, 212, 138, 32)

        self._controls["apps_title"] = self._create_static("Apps", 32, 276, 200, 24, title=True)
        self._controls["app_edit"] = self._create_edit("app.exe", 32, 312, 220, 30)
        self._controls["app_off"] = self._create_button("Off", ID_APP_OFF, 270, 310, 76, 32)
        self._controls["app_limited"] = self._create_button("Limited", ID_APP_LIMITED, 356, 310, 96, 32)
        self._controls["app_on"] = self._create_button("On", ID_APP_ON, 462, 310, 76, 32)
        self._controls["apps_list"] = self._create_listbox(32, 354, 680, 82)

        self._controls["dictionary_title"] = self._create_static("Dictionary", 32, 466, 220, 24, title=True)
        self._controls["dict_edit"] = self._create_edit("word", 32, 502, 220, 30)
        self._controls["dict_add"] = self._create_button("Add", ID_DICT_ADD, 270, 500, 76, 32)
        self._controls["dict_add_never"] = self._create_button("Never correct", ID_DICT_ADD_NEVER, 356, 500, 132, 32)
        self._controls["dict_remove"] = self._create_button("Remove", ID_DICT_REMOVE, 498, 500, 92, 32)
        self._controls["dict_list"] = self._create_listbox(32, 544, 680, 62)

        self._controls["appearance_title"] = self._create_static("Overlay", 32, 632, 200, 24, title=True)
        self._controls["appearance_status"] = self._create_static("", 32, 662, 420, 24)
        self._controls["size_button"] = self._create_button("Cycle size", ID_SIZE, 32, 692, 104, 32)
        self._controls["opacity_button"] = self._create_button("Cycle opacity", ID_OPACITY, 146, 692, 126, 32)
        self._controls["animations_button"] = self._create_button("", ID_ANIMATIONS, 282, 692, 128, 32)

        self._controls["ai_title"] = self._create_static("Local AI", 430, 632, 200, 24, title=True)
        self._controls["ai_status"] = self._create_static("", 430, 662, 286, 24)
        self._controls["ai_toggle"] = self._create_button("", ID_AI_TOGGLE, 430, 692, 76, 32)
        self._controls["ai_provider"] = self._create_button("Provider", ID_AI_PROVIDER, 516, 692, 92, 32)
        self._controls["ai_model_edit"] = self._create_edit("model", 618, 694, 94, 30)
        self._controls["ai_model"] = self._create_button("Save", ID_AI_MODEL, 618, 730, 94, 32)

        self._controls["close_button"] = self._create_button("Close", ID_CLOSE, 32, 730, 104, 32)
        self._refresh_lists()

    def _create_static(self, text: str, x: int, y: int, width: int, height: int, title: bool = False) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "STATIC",
            text,
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
        self._set_control_font(hwnd, title=title)
        return hwnd

    def _create_button(self, text: str, control_id: int, x: int, y: int, width: int, height: int) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "BUTTON",
            text,
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | BS_PUSHBUTTON | BS_FLAT,
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
        self._apply_flat_theme(hwnd)
        return hwnd

    def _create_edit(self, text: str, x: int, y: int, width: int, height: int) -> int:
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
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        return hwnd

    def _create_listbox(self, x: int, y: int, width: int, height: int) -> int:
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
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, height, CONTROL_RADIUS_MM)
        return hwnd

    def _create_combo(self, control_id: int, x: int, y: int, width: int, height: int) -> int:
        hwnd = self.user32.CreateWindowExW(
            0,
            "COMBOBOX",
            "",
            WS_VISIBLE | WS_CHILD | WS_TABSTOP | CBS_DROPDOWNLIST,
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
        self._apply_flat_theme(hwnd)
        self._round_control(hwnd, width, 30, CONTROL_RADIUS_MM)
        return hwnd

    def _combo_add_many(self, name: str, values: list[str]) -> None:
        hwnd = self._controls[name]
        for value in values:
            self.user32.SendMessageW(hwnd, CB_ADDSTRING, 0, ctypes.c_wchar_p(value))

    def _set_combo_index(self, name: str, index: int) -> None:
        self.user32.SendMessageW(self._controls[name], CB_SETCURSEL, index, None)

    def _get_combo_index(self, name: str) -> int:
        return int(self.user32.SendMessageW(self._controls[name], CB_GETCURSEL, 0, None))

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
            return self._handle_control_color(message, w_param)
        if message == WM_DESTROY:
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, message, w_param, l_param)

    def _handle_control_color(self, message: int, device_context: int) -> int:
        self.gdi32.SetTextColor(device_context, TEXT_PRIMARY)
        self.gdi32.SetBkMode(device_context, TRANSPARENT)
        if message in {WM_CTLCOLOREDIT, WM_CTLCOLORLISTBOX}:
            self.gdi32.SetBkColor(device_context, DARK_INPUT)
            return self._brush_input
        if message == WM_CTLCOLORBTN:
            self.gdi32.SetBkColor(device_context, DARK_PANEL)
            return self._brush_panel
        self.gdi32.SetBkColor(device_context, DARK_BACKGROUND)
        return self._brush_background

    def _handle_command(self, control_id: int) -> None:
        if control_id == ID_ASSISTANT_COMBO:
            self.database.set_bool_setting("assistant_enabled", self._get_combo_index("assistant_combo") == 0)
        elif control_id == ID_STRENGTH_COMBO:
            strengths = ["light", "balanced", "aggressive"]
            index = self._get_combo_index("strength_combo")
            if 0 <= index < len(strengths):
                self.database.set_setting("correction_strength", strengths[index])
        elif control_id == ID_LEARNING_COMBO:
            self.database.set_bool_setting("learning_enabled", self._get_combo_index("learning_combo") == 0)
        elif control_id == ID_THEME_COMBO:
            themes = ["dark", "light", "system"]
            index = self._get_combo_index("theme_combo")
            if 0 <= index < len(themes):
                self.database.set_appearance_settings(theme=themes[index])
        elif control_id == ID_CLEAR_LEARNING:
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
