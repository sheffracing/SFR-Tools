import traceback
import wx

from utils.log import log

def handle(func):
    def wrapper(*args, **kwargs):
        from UX.info import InfoDialog
        try:
            result = func(*args, **kwargs)
            return result
        except:
            error = traceback.format_exc()
            log(error)

            # For constructors, args[0] is the object being constructed and
            # args[1] is its wx parent. For other decorated methods, prefer
            # their owning window (or a wx.Window argument) when available.
            parent = kwargs.get("parent")
            if not isinstance(parent, wx.Window):
                parent = None
                for arg in args[1:]:
                    if isinstance(arg, wx.Window):
                        parent = arg
                        break
                if parent is None and args:
                    candidate = getattr(args[0], "parent", None)
                    if isinstance(candidate, wx.Window):
                        parent = candidate

            ui = InfoDialog(parent, "An exception has occurred.", error, "Error", [("Retry", wx.ID_RETRY), ("Close", wx.ID_CLOSE)])
            # Error dialogs must take focus immediately. The normal InfoDialog
            # show() path is modeless, so its caller can otherwise leave it
            # behind KiCad or another plugin window.
            from utils.platform import win32, darwin
            win32.attach_app(ui, ui.__foreground_hwnd, ui.__board)
            darwin.attach_app(ui)
            ui.CentreOnScreen()
            response = ui.ShowModal()
            ui.Destroy()
            if response == wx.ID_RETRY:
                 return wrapper(*args, **kwargs)
    return wrapper


# Only log, do NOT expose to user. Avoids cyclical imports when used in UX.info
def lite(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except:
            log(traceback.format_exc())
    return wrapper