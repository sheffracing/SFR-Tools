import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback
import threading
import importlib
from typing_extensions import Literal
import time

from utils.platform import win32, darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils



class LoiginDialog(wx.Dialog, UIUtils.Entrypoint, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent, code_callback):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Entrypoint.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)

        self.book = wx.Simplebook(self)
        self.pending = Pending(self, code_callback)
        self.book.AddPage(self.pending,"Pending",True)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.book, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)

        self.SetMinSize((380, 300))
        self.CentreOnParent()

class CodeBox(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent, code: str = "ERROR"):
        wx.Panel.__init__(
            self,
            parent
        )
        UIUtils.Constructor.__init__(self, parent)
        self.code = code

        appearance = wx.SystemSettings.GetAppearance()
        dark_mode = appearance.IsDark()

        self.book = wx.Simplebook(self)

        # Text
        self.text_page = wx.Panel(self.book)
        self.text = wx.StaticText(
            self.text_page,
            label=code,
            style=wx.ALIGN_CENTER
        )
        self.text.SetFont(self.code_font)

        self.text_sizer = wx.BoxSizer(wx.VERTICAL)
        self.text_sizer.AddStretchSpacer(1)
        self.text_sizer.Add(self.text, 0, wx.ALIGN_CENTER | wx.TOP, 6)
        self.text_sizer.AddStretchSpacer(1)
        self.text_page.SetSizer(self.text_sizer)


        # Icon
        self.icon_page = wx.Panel(self.book)

        self.icon_display = wx.StaticBitmap(
            self.icon_page,
            bitmap=UIUtils.load_icon(
                "copy.png",
                dark_mode,
                (16, 18),
                False
            )
        )

        self.icon_sizer = wx.BoxSizer(wx.VERTICAL)
        self.icon_sizer.AddStretchSpacer(1)
        self.icon_sizer.Add(self.icon_display, 0, wx.ALIGN_CENTER)
        self.icon_sizer.AddStretchSpacer(1)
        self.icon_page.SetSizer(self.icon_sizer)

        self.book.AddPage(self.text_page, "Code", True)
        self.book.AddPage(self.icon_page, "Copy")
        self.book.SetSelection(0)

        self.text_size = self.text.GetBestSize()

        self.SetMinSize((
            self.text_size.width + 40,
            self.text_size.height + 20
        ))


        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

        self.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.book.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.text.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.icon_display.Bind(wx.EVT_LEFT_DOWN, self.copy_code)

    @misc.handle
    def copy_code(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.code))
            wx.TheClipboard.Close()

        self.book.SetSelection(1)
        wx.CallLater(1000, self.restore)
    @misc.handle
    def restore(self):
        self.book.SetSelection(0)
    misc.handle
    def set_code(self, code: str = "ERROR"):
        self.code = code
        self.text.SetLabel(code)

        self.text.InvalidateBestSize()
        self.text.GetParent().Layout()

        size = self.text.GetBestSize()
        self.SetMinSize((size.width + 40, size.height + 20))

        self.Layout()
        self.GetParent().Layout()


class Pending(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent, code_callback):
        wx.Panel.__init__(
            self,
            parent
        )
        UIUtils.Constructor.__init__(self, parent)

        self.code_callback = code_callback
        self.url = None

        self.title = wx.StaticText(self, label="Sign into GitHub")
        self.title.SetFont(self.title_font)  

        self.description = wx.StaticText(self, label="Enter the code at GitHub")
        self.code_box = CodeBox(self, "WAIT")
        self.code_box.SetBackgroundColour(self.colours["input"])
        self.code_box.SetForegroundColour(self.colours["text"])

        self.open = wx.Button(self, label="Go to GitHub")
        self.open.Bind(wx.EVT_BUTTON, self.open_page)
        self.open.SetDefault()    

        self.retry = wx.Button(self, wx.ID_CLOSE, "Retry")
        self.retry.Bind(wx.EVT_BUTTON, self.regen_code) 
        
        self.close = wx.Button(self, wx.ID_CLOSE, "Cancel")
        self.close.Bind(wx.EVT_BUTTON, self.parent.EndModal) 

        self.sizer = wx.BoxSizer(wx.VERTICAL)    
        self.sizer.Add(self.title, 0, wx.ALL, 15)
        self.sizer.Add(self.description, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.code_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.open, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.retry, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.close, 0, wx.ALIGN_CENTER | wx.ALL, 10)   

        self.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,100)
        self.sizer.Fit(self)    
        self.Fit()  

        self.regen_code()
    @misc.handle
    def open_page(self, event = None):
        if self.url:
            wx.LaunchDefaultBrowser(self.url)
    @misc.handle
    def regen_code(self, event = None):
        code, interval, self.url = self.code_callback()
        self.code_box.set_code(code)
        self.__update_retry_state(min(5, interval))
    @misc.handle
    def __update_retry_state(self, n):
        if n < 0:
            self.retry.SetLabel(f"Retry")
            self.retry.Enable()
        else:
            self.retry.SetLabel(f"Retry in {n}s")
            self.retry.Disable()
            wx.CallLater(1000, self.__update_retry_state, n-1)
