import platform
import sys
import requests
import subprocess
import time
from pathlib import Path

import ctypes
from ctypes import wintypes
from pywinauto import Desktop


SYSTEM = Path(__file__).name.removesuffix(Path(__file__).suffix)

def entrypoint(func):
    def wrapper(*args,**kwargs):
        if sys.platform == SYSTEM:
             return func(*args,**kwargs)
    return wrapper

@entrypoint
def prepare_app(*args):
    pass

@entrypoint
def attach_app(*args):
    pass

def __press_tools_item(window, names):
    """Find and invoke an enabled Tools menu item."""
    window.set_focus()  

    try:
        for n in names:
            window.menu_select(f"Tools->{n}")
            return True
    except Exception as e:
        print(f"Menu selection failed: {e}")

@entrypoint
def modal(title, message, buttons=None, icon="info"):
    if buttons is None:
        buttons = ["OK"]

    MB_OK = 0x00000000
    MB_OKCANCEL = 0x00000001
    MB_ABORTRETRYIGNORE = 0x00000002
    MB_YESNOCANCEL = 0x00000003
    MB_YESNO = 0x00000004
    MB_RETRYCANCEL = 0x00000005
    MB_CANCELTRYCONTINUE = 0x00000006

    MB_ICONERROR = 0x00000010
    MB_ICONQUESTION = 0x00000020
    MB_ICONWARNING = 0x00000030
    MB_ICONINFORMATION = 0x00000040

    # Windows MessageBox buttons are predefined.
    button_types = {
        ("OK",): MB_OK,
        ("OK", "Cancel"): MB_OKCANCEL,
        ("Abort", "Retry", "Ignore"): MB_ABORTRETRYIGNORE,
        ("Yes", "No", "Cancel"): MB_YESNOCANCEL,
        ("Yes", "No"): MB_YESNO,
        ("Retry", "Cancel"): MB_RETRYCANCEL,
        ("Cancel", "Try Again", "Continue"): MB_CANCELTRYCONTINUE,
    }

    button_set = tuple(buttons)
    if button_set not in button_types:
        raise ValueError(
            f"Unsupported Windows MessageBox button combination: {buttons}"
        )

    icons = {
        "none": 0,
        "error": MB_ICONERROR,
        "question": MB_ICONQUESTION,
        "warning": MB_ICONWARNING,
        "info": MB_ICONINFORMATION,
    }

    if icon not in icons:
        raise ValueError(f"Unsupported icon: {icon}")

    MB_SETFOREGROUND = 0x00010000
    MB_TOPMOST = 0x00040000

    result = ctypes.windll.user32.MessageBoxW(
        None,
        str(message),
        str(title),
        button_types[button_set] | icons[icon] |
        MB_SETFOREGROUND | MB_TOPMOST,
    )

    # Map Win32 return codes to zero-based button indexes.
    results = {
        MB_OK: {1: 0},
        MB_OKCANCEL: {1: 0, 2: 1},
        MB_ABORTRETRYIGNORE: {3: 0, 4: 1, 5: 2},
        MB_YESNOCANCEL: {6: 0, 7: 1, 2: 2},
        MB_YESNO: {6: 0, 7: 1},
        MB_RETRYCANCEL: {4: 0, 2: 1},
        MB_CANCELTRYCONTINUE: {2: 0, 10: 1, 11: 2},
    }

    return results[button_types[button_set]].get(result, -1)

@entrypoint
def save():
    desktop = Desktop(backend="uia")

    windows = desktop.windows()
    kicad_windows = [
        window for window in windows
        if "Schematic Editor" in window.window_text()
    ]

    if not kicad_windows:
        return

    for window in kicad_windows:
        title = window.window_text()
        print(f"title: {title}")
        if "Schematic Editor" in title:
            try:
                window.set_focus()
                window.menu_select("File->Save")

            except Exception as e:
                print(f"Failed to save '{title}': {e}")

@entrypoint
def open(eeschema: bool = True, pcbnew: bool = True):
    desktop = Desktop(backend="uia")    
    # Find the KiCad Manager window, excluding editor windows.
    window = next(
        (
            w for w in desktop.windows()
            if "KiCad" in w.window_text()
            and "PCB Editor" not in w.window_text()
            and "Schematic Editor" not in w.window_text()
        ),
        None,
    )   
    if window is None:
        modal(
            "No KiCad Instances detected",
            "Plugin may be unstable if you continue.",
        )
        return    
    if eeschema:
        if not __press_tools_item(window, (
            "Schematic Editor",
            "Switch to Schematic Editor",
        )):
            modal(
                "Schematic Editor Not Found",
                "Could not find an enabled Schematic Editor item "
                "in the KiCad Tools menu.",
            )   
    if pcbnew:
        # Allow the schematic editor time to load before switching focus.
        try:
            window.set_focus()  
            if not __press_tools_item(window, (
                "PCB Editor",
                "Switch to PCB Editor",
            )):
                modal(
                    "PCB Editor Not Found",
                    "Could not find an enabled PCB Editor item "
                    "in the KiCad Tools menu.",
                )   
        except Exception as exc:
            modal("Unable to Open PCB Editor", str(exc))    