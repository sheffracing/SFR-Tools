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

#from utils.log import log

SYSTEM = "darwin"

def entrypoint(func):
    def wrapper(*args,**kwargs):
        if sys.platform == SYSTEM:
             return func(*args,**kwargs)
    return wrapper

if sys.platform == SYSTEM:
    from AppKit import (
        NSAlert,
        NSAlertStyleInformational,
        NSCriticalAlertStyle,
        NSApp,
        NSImage,
        NSApplicationActivationPolicyRegular,
        NSModalResponseOK,
        NSScreen,
        NSAlertFirstButtonReturn,
        NSAlertSecondButtonReturn,
        NSAlertThirdButtonReturn,
        NSWorkspace,
        NSApplication
    )

    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue,
        AXUIElementSetAttributeValue,
        AXUIElementPerformAction,

        kAXWindowsAttribute,
        kAXTitleAttribute,
        kAXFocusedAttribute,
        kAXMainAttribute,
        kAXMenuBarAttribute,
        kAXChildrenAttribute,
        kAXPressAction,
        kAXEnabledAttribute,
        kAXFrontmostAttribute,
        kAXErrorSuccess,
        AXUIElementCopyAttributeNames
    )
    import Quartz


def _objc_runtime():
    import ctypes

    objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    return ctypes, objc

@entrypoint
def prepare_app():
    """Make the wx process an accessory app before creating any windows."""
    try:
        ctypes, objc = _objc_runtime()
        send = objc.objc_msgSend
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        send.restype = ctypes.c_void_p
        app = send(
            objc.objc_getClass(b"NSApplication"),
            objc.sel_registerName(b"sharedApplication"),
        )

        # NSApplicationActivationPolicyAccessory = 1. It can receive focus but
        # does not present itself as an independent Dock application.
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        send.restype = ctypes.c_bool
        send(app, objc.sel_registerName(b"setActivationPolicy:"), 1)
    except Exception:
        # Native integration is cosmetic; do not prevent the plugin from
        # running if a future wxPython/AppKit combination changes its handles.
        pass

@entrypoint
def attach_app(window):
    """Keep a wx dialog visible in the PCB editor's Stage Manager set."""
    try:
        ctypes, objc = _objc_runtime()
        send = objc.objc_msgSend

        # wxWindow::GetHandle() is an NSView on wxOSX. NSWindow also responds
        # to -window by returning itself, which covers either native handle.
        native_handle = ctypes.c_void_p(int(window.GetHandle()))
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        send.restype = ctypes.c_void_p
        ns_window = send(native_handle, objc.sel_registerName(b"window"))
        if not ns_window:
            return

        # NSFloatingWindowLevel. Keep it visible when focus returns to KiCad.
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        send.restype = None
        send(ns_window, objc.sel_registerName(b"setLevel:"), 3)
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        send(ns_window, objc.sel_registerName(b"setHidesOnDeactivate:"), False)

        icon = NSImage.alloc().initWithContentsOfFile(
            "icons/app_icon.png"
        )
        NSApplication.sharedApplication().setApplicationIconImage_(icon)

        # This Stage Manager behavior was introduced with macOS 13. Apple
        # defines it for floating windows that should join other apps' sets.
        major = int(platform.mac_ver()[0].split(".")[0] or 0)
        if major >= 13:
            transient = 1 << 3
            ignores_cycle = 1 << 6
            can_join_all_applications = 1 << 18

            send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            send.restype = ctypes.c_ulong
            behavior = send(
                ns_window, objc.sel_registerName(b"collectionBehavior")
            )
            # Primary and Auxiliary are mutually exclusive with
            # CanJoinAllApplications.
            behavior &= ~((1 << 16) | (1 << 17))
            behavior |= transient | ignores_cycle | can_join_all_applications
            send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            send.restype = None
            send(
                ns_window,
                objc.sel_registerName(b"setCollectionBehavior:"),
                behavior,
            )
    except Exception:
        pass

@entrypoint
def modal(title: str, message: str, buttons: list[str] = ["OK"]):
    alert = NSAlert.alloc().init()

    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    alert.setAlertStyle_(NSCriticalAlertStyle)
    for i in buttons:
        alert.addButtonWithTitle_(i)

    path = (Path(__file__).parent / "icons" / "app_icon.png").absolute()
    icon = NSImage.alloc().initWithContentsOfFile_(str(path))
    alert.setIcon_(icon)

    alert_window = alert.window()
    alert_window.setLevel_(3)  # NSFloatingWindowLevel
    alert_window.setHidesOnDeactivate_(False)

    alert_window.center()

    # Same Stage Manager behavior as attach_to_stage_manager().
    major = int(platform.mac_ver()[0].split(".")[0] or 0)

    if major >= 13:
        from AppKit import (
            NSWindowCollectionBehaviorTransient,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorCanJoinAllApplications,
        )

        behavior = (
            NSWindowCollectionBehaviorTransient
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorCanJoinAllApplications
        )

        alert_window.setCollectionBehavior_(behavior)

    NSApp.activateIgnoringOtherApps_(True)

    response = alert.runModal()

    if response == NSAlertFirstButtonReturn:
        return 0
    elif response == NSAlertSecondButtonReturn:
        return 1
    elif response == NSAlertThirdButtonReturn:
        return 2
    else:
        return None

def __ax_value(element, attribute):
    error, value = AXUIElementCopyAttributeValue(
        element,
        attribute,
        None
    )
    return value if error == 0 else None


def __ax_children(element):
    return __ax_value(element, kAXChildrenAttribute) or []


def __ax_title(element):
    return __ax_value(element, kAXTitleAttribute)


def __find_ax_element(element, title):
    """
    Recursively find an AX element with the given title.
    """
    #print("AX Title: ", __ax_title(element), "target: ", title)
    if __ax_title(element) == title:
        return element

    for child in __ax_children(element):
        result = __find_ax_element(child, title)

        if result is not None:
            return result

    return None

def __click_menu_item(app, menu, item):
    menu_bar = __ax_value(app, kAXMenuBarAttribute)

    if menu_bar is None:
        raise RuntimeError("Could not get menu bar")

    menu_element = __find_ax_element(menu_bar, menu)

    if menu_element is None:
        raise RuntimeError(f"Could not find menu: {menu}")

    item_element = __find_ax_element(menu_element, item)

    if item_element is None:
        raise RuntimeError(
            f"Could not find menu item: {menu} -> {item}"
        )

    enabled = __ax_value(item_element, kAXEnabledAttribute)

    if enabled is False:
        raise RuntimeError(
            f"{menu} -> {item} is disabled"
        )

    error = AXUIElementPerformAction(
        item_element,
        kAXPressAction
    )

    if error != 0:
        raise RuntimeError(
            f"AXUIElementPerformAction failed: {error}"
        )

def __find_window(app, text: str):
    for window in __ax_value(app, kAXWindowsAttribute) or []:
        window_title = __ax_value(window, kAXTitleAttribute) or ""
        if text in window_title:
            return window
    return None


def __focus_window(window):
    error = AXUIElementSetAttributeValue(
        window,
        kAXMainAttribute,
        True
    )

    if error != 0:
        raise RuntimeError(
            f"Could not make window main: {error}"
        )

    error = AXUIElementSetAttributeValue(
        window,
        kAXFocusedAttribute,
        True
    )

    if error != 0:
        raise RuntimeError(
            f"Could not focus window: {error}"
        )

def __activate_application(app):
    # Ask the application to become frontmost
    error = AXUIElementSetAttributeValue(
        app,
        kAXFrontmostAttribute,
        True
    )

    if error != 0:
        print(f"Could not set AXFrontmost: {error}")

    # Ask the application to accept keyboard focus
    #error = AXUIElementSetAttributeValue(
    #    app,
    #    kAXFocusedAttribute,
    #    True
    #)
    #
    #if error != 0:
    #    print(f"Could not set AXFocused: {error}")

#Get the Unique numeric Identifier associated with the currently running KiCad instance
@entrypoint
def get_pid(name: str = "KiCad"):
    # NSWorkspace.sharedWorkspace() only takes a snapshot when the python interpreter starts. Filter pgrep with KiCad's exe path.
    result = subprocess.run(
            ["pgrep", "-afil", "KiCad.app/Contents/MacOS/kicad"],
            capture_output=True,
            text=True
        )
    # output returns the form '{pid} {path}\n'
    pids = [int(pid.split(None, 1)[0]) for pid in result.stdout.splitlines()]
    if len(pids) > 1:
        modal("Multiple KiCad Instances detected", "Plugin may be unstable if you continue.")
    return pids[0] if len(pids) > 0 else None

@entrypoint
def save():
    pid = get_pid("KiCad")
    if not pid:
        modal("No KiCad Instances detected", "Plugin may be unstable if you continue.")
        return
    app = AXUIElementCreateApplication(pid)

    for window in __ax_value(app, kAXWindowsAttribute) or []:
        title = __ax_value(window, kAXTitleAttribute) or ""
        # Get the pcbnew and eeshcema windows (if present)
        if "PCB Editor" in title or "Schematic Editor" in title:
            __activate_application(app)
            __focus_window(window)
            # Trigger Save topbar button
            __click_menu_item(
                app,
                "File",
                "Save"
            )

@entrypoint
def open(eeschema: bool = True, pcbnew: bool = True):
    pid = get_pid("KiCad")
    if not pid:
        modal("No KiCad Instances detected", "Plugin may be unstable if you continue.")
        return
    app = AXUIElementCreateApplication(pid)
    window = __find_window(app, "KiCad")

    __activate_application(app)
    __focus_window(window)

    # Get the Tools > eeschema/pcbnew buttons. A simple way to programmatically open these apps with KiCad as the parent. 
    menu = __ax_value(app, kAXMenuBarAttribute)
    if not menu:
        modal("MenuBarAttribute Not Found", "Plugin may be unstable if you continue.")
        return
    
    tools = __find_ax_element(menu, "Tools")
    if not tools:
        modal("AXElement 'Tools' Not Found", "Plugin may be unstable if you continue.")
        return

    if eeschema:
        open_sch = __find_ax_element(tools, "Schematic Editor")
        switch_sch = __find_ax_element(tools, "Switch to Schematic Editor")
        active_sch = open_sch or switch_sch
        enabled = active_sch and __ax_value(active_sch, kAXEnabledAttribute)
        if enabled:
            # Press the eeschema button
            AXUIElementPerformAction(
                active_sch,
                kAXPressAction
            )
    if pcbnew:
        # If eeschema has just opened, it will be pulled to the front and actions will be disabled while it loads.
        # TODO: Is there an attribute we can listen for to check the window can accept AXAPI triggers now?
        time.sleep(2)
        __activate_application(app)
        __focus_window(window)
        open_pcb = __find_ax_element(tools, "PCB Editor")
        switch_pcb = __find_ax_element(tools, "Switch to PCB Editor")
        active_pcb = open_pcb or switch_pcb

        enabled = active_pcb and __ax_value(active_pcb, kAXEnabledAttribute)
        if enabled:
            # Press the pcbnew button
            AXUIElementPerformAction(
                active_pcb,
                kAXPressAction
            )
