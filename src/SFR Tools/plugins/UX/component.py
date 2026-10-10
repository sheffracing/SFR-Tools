import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback
import threading
import importlib
from typing_extensions import Literal
import time
import re

from utils.platform import win32, darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils

class Component(wx.Dialog, UIUtils.Worker ,UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Worker.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)

        self.title = wx.StaticText(self, label="Add a new Symbol or Footprint")
        self.title.SetFont(self.title_font)  
        self.description = wx.StaticText(self, label="Add a custom component to our Shared Library. \n\nAccepted Files:\n• .kicad_sym\n• .kicad_mod")
        self.description.Wrap(260)

        self.drop = DragDropFile(self)

        self.error = wx.StaticText(self, label="File Invalid")
        self.error.SetForegroundColour(wx.RED)
        self.error.Hide()

        self.upload = wx.Button(self, wx.ID_CLOSE, "Add ? File")
        self.upload.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES)) 
        self.upload.Hide()

        close = wx.Button(self, wx.ID_CANCEL, "Cancel")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.title, 0, wx.ALL, 15)
        self.sizer.Add(self.description, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.drop, 0, wx.EXPAND | wx.ALL, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.upload, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)   

        self.SetSizer(self.sizer)
        self.Fit()
    @misc.handle
    def refresh(self):
        self.sizer.Layout()
        self.Layout()
        self.Fit()
    @misc.handle
    def onFile(self):
        self.error.Hide()
        self.upload.SetLabel(f"Add {len(self.drop.files)} File{'s' if len(self.drop.files) >1 else ''}")
        self.upload.Show()
        self.refresh()
    @misc.handle
    def onInvalidFile(self):
        self.error.Show()
        self.refresh()

class FileDrop(wx.FileDropTarget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
    @misc.handle
    def OnDropFiles(self, x: int = None, y: int = None, files: list[str] = []):
        valid = True
        for file in files:
            valid = valid and re.search("\.kicad_(sym|mod)$", file) != None
        if valid:
            self.parent.files.extend(files)
            self.parent.parent.onFile()
        else:
            self.parent.parent.onInvalidFile()
        return valid
    @misc.handle
    def OnEnter(self, x, y, d):
        return wx.DragCopy
    @misc.handle
    def OnDragOver(self, x, y, d):
        return wx.DragCopy
   
class DragDropFile(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent):
        wx.Panel.__init__(
            self,
            parent,
            style=wx.BORDER_SIMPLE
        )
        UIUtils.Constructor.__init__(self, parent)

        self.parent = parent
        self.files = []

        self.drop_targets = [FileDrop(self) for _ in range(3)]
    
        self.desc = wx.StaticText(self,label=f"Drag && Drop", style=wx.ALIGN_CENTER)
        self.icon = wx.StaticBitmap(self, bitmap=UIUtils.load_icon("download.png", False, (40, 40)))

        self.SetDropTarget(self.drop_targets[0])
        self.desc.SetDropTarget(self.drop_targets[1])
        self.icon.SetDropTarget(self.drop_targets[2])

        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.desc.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.icon.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        self.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.desc.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.icon.Bind(wx.EVT_LEFT_DOWN, self.on_click)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.desc, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.SetSizerAndFit(sizer)

    @misc.handle
    def on_click(self, event):
        with wx.FileDialog(
            self,
            "Select a file",
            wildcard=(
                "KiCad Symbol (*.kicad_sym)|*.kicad_sym|"
                "KiCad Footprint (*.kicad_mod)|*.kicad_mod|"
            ),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                filepath = dialog.GetPath()
                if re.search("\.kicad_(sym|mod)$", filepath) != None:
                    self.files.append(filepath)
                    self.parent.onFile()
                else:
                    self.parent.onInvalidFile()
