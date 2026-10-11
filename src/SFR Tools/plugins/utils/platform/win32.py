# macOS dialog integration for Stage Manager.
#
# An IPC plugin runs in its own process, so macOS normally treats its wx dialog
# as a separate application and pushes the PCB editor into the background.
#
# License: GPL-3.0-or-later

import platform
import sys
import requests
import subprocess
import time
from pathlib import Path

import ctypes
from ctypes import wintypes
from pywinauto import Desktop


SYSTEM = "darwin"

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
    # Open Tools through the menu bar.
    window.menu_select("Tools") 
    # Search the UI Automation tree for the requested item.
    for item in window.descendants(control_type="MenuItem"):
        if item.window_text().strip() in names:
            if item.is_enabled():
                item.click_input()
                return True 
    return False  

@entrypoint
def modal(title: str, message: str, buttons: list[str] = ["OK"]):
    if not buttons:
        return None
    comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    class TASKDIALOG_BUTTON(ctypes.Structure):
        _fields_ = [
            ("nButtonID", ctypes.c_int),
            ("pszButtonText", wintypes.LPCWSTR),
        ]
    class TASKDIALOGCONFIG(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwndParent", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("dwFlags", wintypes.DWORD),
            ("dwCommonButtons", ctypes.c_int),
            ("pszWindowTitle", wintypes.LPCWSTR),
            ("mainIcon", ctypes.c_void_p),
            ("pszMainInstruction", wintypes.LPCWSTR),
            ("pszContent", wintypes.LPCWSTR),
            ("cButtons", ctypes.c_uint),
            ("pButtons", ctypes.POINTER(TASKDIALOG_BUTTON)),
            ("nDefaultButton", ctypes.c_int),
            ("cRadioButtons", ctypes.c_uint),
            ("pRadioButtons", ctypes.c_void_p),
            ("nDefaultRadioButton", ctypes.c_int),
            ("pszVerificationText", wintypes.LPCWSTR),
            ("pszExpandedInformation", wintypes.LPCWSTR),
            ("pszExpandedControlText", wintypes.LPCWSTR),
            ("pszCollapsedControlText", wintypes.LPCWSTR),
            ("pszFooter", wintypes.LPCWSTR),
            ("pfCallback", ctypes.c_void_p),
            ("lpCallbackData", ctypes.c_longlong),
            ("cxWidth", ctypes.c_uint),
        ]
    # Load the application icon from the existing PNG.
    # Windows LoadImage supports BMP/ICO, not PNG.
    # Use the executable/module icon if one is available.
    hinstance = kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    hinstance = kernel32.GetModuleHandleW(None)
    # Task dialog icon: use the native error icon.
    TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
    TDF_SIZE_TO_CONTENT = 0x01000000
    TD_ERROR_ICON = ctypes.c_void_p(-1)
    button_array = (TASKDIALOG_BUTTON * len(buttons))(
        *[
            TASKDIALOG_BUTTON(i + 100, label)
            for i, label in enumerate(buttons)
        ]
    )
    config = TASKDIALOGCONFIG()
    config.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    config.hwndParent = None
    config.hInstance = hinstance
    config.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_SIZE_TO_CONTENT
    config.dwCommonButtons = 0
    config.pszWindowTitle = title
    config.mainIcon = TD_ERROR_ICON
    config.pszMainInstruction = title
    config.pszContent = message
    config.cButtons = len(buttons)
    config.pButtons = button_array
    config.nDefaultButton = 100
    selected = ctypes.c_int()
    comctl32.TaskDialogIndirect.argtypes = [
        ctypes.POINTER(TASKDIALOGCONFIG),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(wintypes.BOOL),
    ]
    comctl32.TaskDialogIndirect.restype = ctypes.c_long
    result = comctl32.TaskDialogIndirect(
        ctypes.byref(config),
        ctypes.byref(selected),
        None,
        None,
    )
    if result != 0:
        raise ctypes.WinError(result)
    if selected.value == 0:
        return None
    index = selected.value - 100
    return index if 0 <= index < len(buttons) else None

@entrypoint
def save():
    desktop = Desktop(backend="uia")

    # Find all KiCad windows
    windows = desktop.windows()

    kicad_windows = [
        window for window in windows
        if "KiCad" in window.window_text()
    ]

    if not kicad_windows:
        modal(
            "No KiCad Instances detected",
            "Plugin may be unstable if you continue."
        )
        return

    for window in kicad_windows:
        title = window.window_text()

        # Get the PCB and Schematic Editor windows
        if "PCB Editor" in title or "Schematic Editor" in title:
            try:
                # Activate and focus this window
                window.set_focus()

                # Trigger File > Save
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
        if not __press_tools_item((
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
        if eeschema:
            time.sleep(2)   
        try:
            window.set_focus()  
            if not __press_tools_item((
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