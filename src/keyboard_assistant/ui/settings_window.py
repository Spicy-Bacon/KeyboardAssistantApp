from __future__ import annotations

import ctypes
from ctypes import wintypes

from keyboard_assistant.storage.database import Database


WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_SETTEXT = 0x000C
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
BS_PUSHBUTTON = 0x00000000
SS_LEFT = 0x00000000
ES_AUTOHSCROLL = 0x0080
LBS_NOTIFY = 0x0001
WS_VSCROLL = 0x00200000
LB_ADDSTRING = 0x0180
LB_RESETCONTENT = 0x0184
CW_USEDEFAULT = -2147483648
SW_SHOW = 5

ID_TOGGLE_ASSISTANT = 101
ID_CYCLE_STRENGTH = 102
ID_TOGGLE_LEARNING = 103
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

WndProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
) if hasattr(ctypes, "WINFUNCTYPE") else None

HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HINSTANCE = getattr(wintypes, "HINSTANCE", wintypes.HANDLE)
HMENU = getattr(wintypes, "HMENU", wintypes.HANDLE)


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


class SettingsWindow:
    def __init__(self, database: Database) -> None:
        if not hasattr(ctypes, "windll") or WndProc is None:
            raise RuntimeError("Settings window is currently Windows-only.")
        self.database = database
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.kernel32 = ctypes.windll.kernel32
        self._configure_win32_api()
        self._wnd_proc_ref = WndProc(self._wnd_proc)
        self._class_name = f"KeyboardAssistantSettingsWindow{id(self)}"
        self._class_registered = False
        self._initializing = True
        self._controls: dict[str, int] = {}
        self._register_class()
        self.hwnd = self._create_window()
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

    def refresh(self) -> None:
        settings = self.database.get_settings()
        summary = self.database.data_summary()
        self._set_text("status", f"Assistant: {'On' if settings.assistant_enabled else 'Off'}")
        self._set_text("strength", f"Correction strength: {settings.correction_strength.title()}")
        self._set_text("learning", f"Learning: {'On' if settings.learning_enabled else 'Off'}")
        self._set_text(
            "data",
            "Local data: "
            f"{summary['personal_dictionary']} dictionary words, "
            f"{summary['accepted_suggestions']} accepted, "
            f"{summary['ignored_suggestions']} ignored, "
            f"{summary['reverted_corrections']} reverted",
        )
        self._set_text("assistant_button", "Turn Assistant Off" if settings.assistant_enabled else "Turn Assistant On")
        self._set_text("learning_button", "Turn Learning Off" if settings.learning_enabled else "Turn Learning On")
        appearance = self.database.get_appearance_settings()
        self._set_text(
            "appearance_status",
            f"Theme: {appearance.theme.title()} | Size: {appearance.suggestion_size.title()} | "
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
        instance = self.kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASS()
        wndclass.lpfnWndProc = self._wnd_proc_ref
        wndclass.hInstance = instance
        wndclass.lpszClassName = self._class_name
        wndclass.hbrBackground = self.gdi32.CreateSolidBrush(0x00F7F7F7)
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
            520,
            870,
            0,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _create_controls(self) -> None:
        self._controls["status"] = self._create_static("", 24, 24, 440, 24)
        self._controls["strength"] = self._create_static("", 24, 54, 440, 24)
        self._controls["learning"] = self._create_static("", 24, 84, 440, 24)
        self._controls["data"] = self._create_static("", 24, 124, 460, 24)
        self._controls["assistant_button"] = self._create_button("", ID_TOGGLE_ASSISTANT, 24, 170, 150, 34)
        self._controls["strength_button"] = self._create_button("Cycle Strength", ID_CYCLE_STRENGTH, 184, 170, 140, 34)
        self._controls["learning_button"] = self._create_button("", ID_TOGGLE_LEARNING, 334, 170, 150, 34)
        self._controls["clear_button"] = self._create_button("Clear Learning", ID_CLEAR_LEARNING, 24, 218, 150, 34)
        self._controls["close_button"] = self._create_button("Close", ID_CLOSE, 334, 218, 150, 34)

        self._controls["apps_title"] = self._create_static("Apps", 24, 276, 200, 24)
        self._controls["app_edit"] = self._create_edit("app.exe", 24, 306, 190, 26)
        self._controls["app_off"] = self._create_button("Off", ID_APP_OFF, 224, 304, 74, 30)
        self._controls["app_limited"] = self._create_button("Limited", ID_APP_LIMITED, 306, 304, 82, 30)
        self._controls["app_on"] = self._create_button("On", ID_APP_ON, 396, 304, 74, 30)
        self._controls["apps_list"] = self._create_listbox(24, 342, 446, 86)

        self._controls["dictionary_title"] = self._create_static("Dictionary", 24, 454, 200, 24)
        self._controls["dict_edit"] = self._create_edit("word", 24, 484, 190, 26)
        self._controls["dict_add"] = self._create_button("Add", ID_DICT_ADD, 224, 482, 74, 30)
        self._controls["dict_add_never"] = self._create_button("Never Correct", ID_DICT_ADD_NEVER, 306, 482, 116, 30)
        self._controls["dict_remove"] = self._create_button("Remove", ID_DICT_REMOVE, 430, 482, 82, 30)
        self._controls["dict_list"] = self._create_listbox(24, 522, 488, 58)

        self._controls["appearance_title"] = self._create_static("Appearance", 24, 608, 200, 24)
        self._controls["appearance_status"] = self._create_static("", 24, 638, 460, 24)
        self._controls["theme_button"] = self._create_button("Cycle Theme", ID_THEME, 24, 668, 112, 30)
        self._controls["size_button"] = self._create_button("Cycle Size", ID_SIZE, 144, 668, 104, 30)
        self._controls["opacity_button"] = self._create_button("Cycle Opacity", ID_OPACITY, 256, 668, 116, 30)
        self._controls["animations_button"] = self._create_button("", ID_ANIMATIONS, 380, 668, 132, 30)

        self._controls["ai_title"] = self._create_static("Local AI", 24, 720, 200, 24)
        self._controls["ai_status"] = self._create_static("", 24, 750, 460, 24)
        self._controls["ai_toggle"] = self._create_button("", ID_AI_TOGGLE, 24, 780, 96, 30)
        self._controls["ai_provider"] = self._create_button("Cycle Provider", ID_AI_PROVIDER, 128, 780, 126, 30)
        self._controls["ai_model_edit"] = self._create_edit("model", 262, 782, 150, 26)
        self._controls["ai_model"] = self._create_button("Save Model", ID_AI_MODEL, 420, 780, 92, 30)
        self._refresh_lists()

    def _create_static(self, text: str, x: int, y: int, width: int, height: int) -> int:
        return self.user32.CreateWindowExW(
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

    def _create_button(self, text: str, control_id: int, x: int, y: int, width: int, height: int) -> int:
        return self.user32.CreateWindowExW(
            0,
            "BUTTON",
            text,
            WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
            x,
            y,
            width,
            height,
            self.hwnd,
            control_id,
            self.kernel32.GetModuleHandleW(None),
            None,
        )

    def _create_edit(self, text: str, x: int, y: int, width: int, height: int) -> int:
        return self.user32.CreateWindowExW(
            0,
            "EDIT",
            text,
            WS_VISIBLE | WS_CHILD | WS_BORDER | ES_AUTOHSCROLL,
            x,
            y,
            width,
            height,
            self.hwnd,
            0,
            self.kernel32.GetModuleHandleW(None),
            None,
        )

    def _create_listbox(self, x: int, y: int, width: int, height: int) -> int:
        return self.user32.CreateWindowExW(
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
        if message == WM_DESTROY:
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, message, w_param, l_param)

    def _handle_command(self, control_id: int) -> None:
        settings = self.database.get_settings()
        if control_id == ID_TOGGLE_ASSISTANT:
            self.database.set_bool_setting("assistant_enabled", not settings.assistant_enabled)
        elif control_id == ID_CYCLE_STRENGTH:
            strengths = ["light", "balanced", "aggressive"]
            index = strengths.index(settings.correction_strength) if settings.correction_strength in strengths else 1
            self.database.set_setting("correction_strength", strengths[(index + 1) % len(strengths)])
        elif control_id == ID_TOGGLE_LEARNING:
            self.database.set_bool_setting("learning_enabled", not settings.learning_enabled)
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
        self.user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]
