import wx
import wx.adv

from pathlib import Path
import traceback
import threading
import time
import re

from utils.platform import win32, darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils
from UX.info import InfoDialog



class Save(wx.Dialog, UIUtils.Worker ,UIUtils.Constructor):
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

        self.title = wx.StaticText(self.panel, label="Save to GitHub")
        self.title.SetFont(self.title_font)

        self.summary_label = wx.StaticText(self.panel, label="Summary of changes")
        self.summary = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.summary.SetHint("Short summary of your changes.")
        self.summary.Bind(wx.EVT_KILL_FOCUS, self.on_summary)

        self.description = UIUtils.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, placeholder="Describe your changes (optional)")
        self.description.SetMinSize((-1, self.description.GetCharHeight() * 4))

        self.error = wx.StaticText(self.panel, label="This question is required")
        self.error.SetForegroundColour(wx.RED)
        wx.CallLater(1, self.error.Hide)

        self.save = wx.Button(self.panel, label="Save")
        self.save.Bind(wx.EVT_BUTTON, self.try_exit)
        self.save.SetDefault()

        self.close = wx.Button(self.panel, wx.ID_CLOSE, "Cancel")
        self.close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.title, 0, wx.ALL, 15)
        self.sizer.Add(self.summary_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.summary, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.save, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,100)
        self.sizer.Fit(self.panel)
        self.Fit()

    @misc.handle
    def on_summary(self, event):
        text = self.summary.GetValue()
        self.fufilled = re.search(r"[A-Za-z0-9]", text)
        if self.fufilled:
            self.error.Hide()
            self.summary.SetBackgroundColour(wx.NullColour)
            self.summary.Refresh()
        else:
            self.summary.SetBackgroundColour(wx.Colour(255, 220, 220))
            self.error.SetLabelText("This question is required")
            self.error.Show()
            self.error.GetParent().Layout()
            self.error.Fit()
            self.error.Refresh()
        if event:
            event.Skip()

    @misc.handle
    def try_exit(self, event):
        self.on_summary(None)
        if not self.fufilled:
            return
        success, data = self.callback["success"](self, self.summary.GetValue(), self.description.GetValue())
        if not success:
            ui = InfoDialog(self, "An exception has occured", str(data["error"]), "Error")
            ui.show()
        else:
            self.EndModal(wx.ID_SAVE)



        