from __future__ import annotations

import ctypes
from ctypes import wintypes
from importlib import resources


IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512


def load_app_icon(user32: object, width: int = 0, height: int = 0) -> tuple[int, bool]:
    """Return (hicon, owned), falling back to the default application icon."""

    _configure_user32(user32)
    try:
        with resources.as_file(resources.files("keyboard_assistant.assets").joinpath("app_icon.ico")) as icon_path:
            icon = int(
                user32.LoadImageW(
                    None,
                    str(icon_path),
                    IMAGE_ICON,
                    width,
                    height,
                    LR_LOADFROMFILE | (LR_DEFAULTSIZE if width == 0 and height == 0 else 0),
                )
                or 0
            )
    except Exception:
        icon = 0
    if icon:
        return icon, True
    return int(user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION)) or 0), False


def destroy_app_icon(user32: object, icon: int, owned: bool) -> None:
    if owned and icon:
        try:
            user32.DestroyIcon(icon)
        except Exception:
            pass


def _configure_user32(user32: object) -> None:
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HANDLE
    user32.DestroyIcon.argtypes = [wintypes.HANDLE]
    user32.DestroyIcon.restype = wintypes.BOOL
