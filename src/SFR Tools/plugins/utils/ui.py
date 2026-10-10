import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback

from utils.platform import win32
from utils.platform import darwin
from utils.log import log
from utils import settings, build

from kipy import KiCad
from kipy.errors import ConnectionError as KiCadConnectionError

# wxWidgets supports one application object per process. Keep it alive for the
# lifetime of the plugin process instead of tying it to an individual dialog.
_wx_app = None

def get_theme_colours():
    if wx.SystemSettings.GetAppearance().IsDark():
        return {
            "background": wx.Colour(30, 30, 30),
            "text": wx.Colour(240, 240, 240),
            "secondary": wx.Colour(180, 180, 180),
            "input": wx.Colour(45, 45, 45),
            "button": wx.Colour(60, 60, 60),
        }
    else:
        return {
            "background": wx.Colour(245, 245, 245),
            "text": wx.Colour(30, 30, 30),
            "secondary": wx.Colour(90, 90, 90),
            "input": wx.Colour(255, 255, 255),
            "button": wx.Colour(235, 235, 235),
        }
    
def load_icon(path:str, dark_mode, size=(24, 24), exclude_path_filter: bool = False):
    if not exclude_path_filter:
        img_path = (Path(__file__).parents[1] / "icons" / path).absolute()
    else:
        img_path = path

    image = wx.Image(str(img_path))

    # Invert black icon to white for dark mode
    if dark_mode:
        image = image.ConvertToGreyscale()

        width, height = image.GetWidth(), image.GetHeight()

        for x in range(width):
            for y in range(height):
                if image.HasAlpha():
                    alpha = image.GetAlpha(x, y)
                else:
                    alpha = 255

                # invert RGB
                value = 255 - image.GetRed(x, y)

                image.SetRGB(x, y, value, value, value)

                if image.HasAlpha():
                    image.SetAlpha(x, y, alpha)

    image = image.Scale(
        size[0],
        size[1],
        wx.IMAGE_QUALITY_HIGH
    )

    return wx.Bitmap(image)

def show(func):
    def wrapper(self, *args,**kwargs):
        try:
            func(self,*args,**kwargs)
            win32.attach_app(self, self.__foreground_hwnd, self.__board)
            darwin.attach_app(self)
            self.CentreOnScreen()
            result = self.ShowModal()
            self.Destroy()
            return result
        except:
            self.Destroy()
    return wrapper

def show_no_yeild(func):
    def wrapper(self,*args,**kwargs):
        try:
            func(self,*args,**kwargs)
            win32.attach_app(self, self.__foreground_hwnd, self.__board)
            darwin.attach_app(self)
            self.CentreOnScreen()
            self.Show()
        except:
            log(traceback.format_exc())
            self.Destroy()
    return wrapper

def app(func):
    def wrapper(self,*args,**kwargs):
        global _wx_app

        self.__foreground_hwnd = win32.prepare_app()
        darwin.prepare_app()

        if _wx_app is None:
            _wx_app = wx.GetApp() or wx.App()
        # Retain the app on the dialog too for compatibility with existing
        # code, while the module reference keeps it alive after dialogs close.
        self.__app = _wx_app

        try:
            kicad = KiCad()
            self.__board = kicad.get_board()
        except KiCadConnectionError:
            wx.MessageBox(
                "Could not connect to KiCad.\n\n"
                "Enable the API server in Preferences > Plugins, and make sure a "
                "board is open in the PCB editor.",
                "SFR", wx.OK | wx.ICON_ERROR,
            )
            return
        
        try:
            a = func(self,*args,**kwargs)
            return a
        except Exception as e:
            log(traceback.format_exc())
    return wrapper

def owned(func):
    def wrapper(self, *args, **kwargs):
        if func:
            func(self, *args, **kwargs)
        assert self.parent
        position = self.parent.ClientToScreen((0, 0))
        size = self.parent.GetClientSize()
        x = position.x
        y = position.y + size.height + 15
        
        self.SetPosition((x,y))
        result = self.ShowModal()
        self.Destroy()    
        return result
    return wrapper

class Constructor():
    def __init__(self, parent):
        self.title_font = wx.Font(
            16,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD
        )
    
        self.normal_font = wx.Font(
            14,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )
    
        self.code_font = wx.Font(
            24,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD
        )
        self.verbatim_font = wx.Font(
            14,
            wx.FONTFAMILY_TELETYPE,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD
        )

        self.colours = get_theme_colours()
        self.dark_mode = wx.SystemSettings.GetAppearance().IsDark()
        self.SetBackgroundColour(self.colours["background"])
        self.parent = parent

        if hasattr(self, "SetIcon"):
            icon = wx.Icon()
            icon.CopyFromBitmap(load_icon("icon.png", self.dark_mode, (24,24)))
            self.SetIcon(icon)

class Entrypoint():
    def __init__(self, parent, *args, **kwargs):
        global _wx_app
        self.parent = parent
        self.__foreground_hwnd = win32.prepare_app()
        darwin.prepare_app()

        if _wx_app is None:
            _wx_app = wx.GetApp() or wx.App()
        self.__app = _wx_app

        try:
            kicad = KiCad()
            self.__board = kicad.get_board()
        except KiCadConnectionError:
            raise KiCadConnectionError("Could not connect to KiCad IPC API.")
        
    def show(self, yeild: bool = True):
        win32.attach_app(self, self.__foreground_hwnd, self.__board)
        darwin.attach_app(self)
        self.CentreOnScreen()
        if yeild:
            result = self.ShowModal()
            self.Destroy()
            return result
        else:
            self.Show()

class Worker():
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        
    def show(self, yeild: bool = False):
        if self.parent:
            position = self.parent.ClientToScreen((0, 0))
            size = self.parent.GetClientSize()
            x = position.x
            y = position.y + size.height + 15
            self.SetPosition((x,y))
        if yeild:
            result = self.ShowModal()  
            return result
        else:
            self.Show()

class TextCtrl(wx.TextCtrl):
    def __init__(self, parent, placeholder="", **kwargs):
        super().__init__(
            parent,
            **kwargs
        )

        self.placeholder = placeholder
        self.showing_placeholder = False

        self._show_placeholder()

        self.Bind(wx.EVT_SET_FOCUS, self._on_focus)
        self.Bind(wx.EVT_KILL_FOCUS, self._on_blur)

    def _show_placeholder(self):
        self.SetValue(self.placeholder)
        self.SetForegroundColour(wx.Colour(150, 150, 150))
        self.showing_placeholder = True

    def _on_focus(self, event):
        if self.showing_placeholder:
            self.SetValue("")
            self.SetForegroundColour(wx.SystemSettings.GetColour(
                wx.SYS_COLOUR_WINDOWTEXT
            ))
            self.showing_placeholder = False
        event.Skip()

    def _on_blur(self, event):
        if not self.GetValue():
            self._show_placeholder()
        event.Skip()

    def GetValue(self):
        if self.showing_placeholder:
            return ""
        return super().GetValue()
