import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback
import time
import re

from utils.platform import win32, darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils

class Review(wx.Dialog, UIUtils.Worker, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent, callbacks):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Worker.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)

        self.callback = callbacks
        self.fufilled = False   
        self.panel = wx.Panel(self)  

        self.title = wx.StaticText(self.panel, label="Send PCB for review")
        self.title.SetFont(self.title_font)  

        self.description_label = wx.StaticText(self.panel, label="Description of Board & Changes")
        self.description = UIUtils.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, placeholder="Describe the board and/or changes you have made.\n You can come back and edit the request on Github later.")
        self.description.SetMinSize((-1, self.description.GetCharHeight() * 4))
        self.description.Bind(wx.EVT_KILL_FOCUS, self.on_desc)  

        self.error = wx.StaticText(self.panel, label="This question is required")
        self.error.SetForegroundColour(wx.RED)
        wx.CallLater(1, self.error.Hide)

        self.request = wx.Button(self.panel, label="Request Review")
        self.request.Bind(wx.EVT_BUTTON, self.try_exit)
        self.request.SetDefault()    

        self.close = wx.Button(self.panel, wx.ID_CLOSE, "Cancel")
        self.close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE)) 

        self.sizer = wx.BoxSizer(wx.VERTICAL)    
        self.sizer.Add(self.title, 0, wx.ALL, 15)
        self.sizer.Add(self.description_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.request, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.close, 0, wx.ALIGN_CENTER | wx.ALL, 10)   

        self.panel.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,100)
        self.sizer.Fit(self.panel)    
        self.Fit()  

    @misc.handle
    def on_desc(self, event = None):
        text = self.description.GetValue()
        self.fufilled = re.search(r"[A-Za-z0-9]", text)
        if self.fufilled:
            self.error.Hide()
            self.description.SetBackgroundColour(wx.NullColour)
            self.description.Refresh()
        else:
            self.description.SetBackgroundColour(wx.Colour(255, 220, 220))
            self.error.SetLabelText("This question is required")
            self.error.Show()
        if event:
            event.Skip()

    @misc.handle
    def try_exit(self, event = None):
        self.on_desc(None)
        if not self.fufilled:
            return
        self.callback["success"](self, self.description.GetValue())
