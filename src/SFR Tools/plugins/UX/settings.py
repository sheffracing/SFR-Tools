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



class SettingsDialog(wx.Dialog, UIUtils.Worker ,UIUtils.Constructor):
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

        self.panel = wx.Panel(self)

        self.title = wx.StaticText(self.panel, label="Preferences")
        self.title.SetFont(self.title_font)
        self.description = wx.StaticText(self.panel, label="Change settings specific to your installation.")
        self.description.SetFont(self.normal_font)
        self.description.SetForegroundColour(self.colours["secondary"])
        self.line = wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL)

        self.other = Other(self.panel)
        self.autosave = Autosave(self.panel)
        self.debug = Debugging(self.panel)

        self.close = wx.Button(self.panel, wx.ID_CLOSE, "Cancel")
        self.close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.title, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.description, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.Add(self.line, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddSpacer(5)
        self.sizer.Add(self.other, 0, wx.EXPAND)
        self.sizer.Add(self.autosave, 0, wx.EXPAND)
        self.sizer.Add(self.debug, 0, wx.EXPAND)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,100)
        self.sizer.Fit(self.panel)
        self.Fit() 


class Debugging(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent):
        wx.Panel.__init__(
            self,
            parent
        )
        UIUtils.Constructor.__init__(self, parent)

        self.note_font = wx.Font(
            11,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )
        self.minor_font = wx.Font(
            13,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )

        self.title = wx.StaticText(self, label="Debugging")
        self.title.SetFont(self.title_font)
        self.description = wx.StaticText(self, label="Debugging preferences")
        self.description.SetFont(self.normal_font)
        self.description.SetForegroundColour(self.colours["secondary"])
        self.line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)

        self.remote_toggle = wx.CheckBox(self, label="Enable Remote Logging")
        self.rl_desc = wx.StaticText(self, label="Remote Logging URL")
        self.rl_desc.SetFont(self.minor_font)
        self.remote_url = UIUtils.TextCtrl(self, placeholder="127.0.0.1:7084")
        self.rl_note = wx.StaticText(self, label="Data will be sent via a POST to /log endpoint.")
        self.rl_note.SetFont(self.note_font)
        self.rl_note.SetForegroundColour(self.colours["secondary"])
        self.line2 = wx.StaticLine(self, style=wx.LI_HORIZONTAL)

        self.local_toggle = wx.CheckBox(self, label="Enable Local Logging")
        self.lcl_desc = wx.StaticText(self, label="Log filepath")
        self.lcl_desc.SetFont(self.minor_font)
        self.local_path = UIUtils.TextCtrl(self, placeholder="/log.txt")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.title, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.description, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.Add(self.line, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddSpacer(10)

        self.sizer.Add(self.remote_toggle, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.rl_desc, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(7)
        self.sizer.Add(self.remote_url, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.rl_note, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.Add(self.line2, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddSpacer(10)

        self.sizer.Add(self.local_toggle, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.lcl_desc, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(7)
        self.sizer.Add(self.local_path, 0, wx.LEFT | wx.RIGHT, 15)

        self.SetSizer(self.sizer)
        self.Layout()


class Autosave(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent):
        wx.Panel.__init__(
            self,
            parent
        )
        UIUtils.Constructor.__init__(self, parent)

        self.note_font = wx.Font(
            11,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )
        self.minor_font = wx.Font(
            13,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )

        self.title = wx.StaticText(self, label="Autosave")
        self.title.SetFont(self.title_font)
        self.description = wx.StaticText(self, label="Autosave preferences")
        self.description.SetFont(self.normal_font)
        self.description.SetForegroundColour(self.colours["secondary"])
        self.line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)

        self.as_toggle = wx.CheckBox(self, label="Enable Autosaving")
        self.as_interval_label = wx.StaticText(self, label="Autosave Interval (mins)")
        self.as_interval_label.SetFont(self.minor_font)
        self.as_interval = UIUtils.TextCtrl(self, placeholder="10")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.title, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.description, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.Add(self.line, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddSpacer(10)

        self.sizer.Add(self.as_toggle, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.as_interval_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(7)
        self.sizer.Add(self.as_interval, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)

        self.SetSizer(self.sizer)
        self.Layout()

class Other(wx.Panel, UIUtils.Constructor):
    @misc.handle
    def __init__(self, parent):
        wx.Panel.__init__(
            self,
            parent
        )
        UIUtils.Constructor.__init__(self, parent)

        self.note_font = wx.Font(
            11,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )
        self.minor_font = wx.Font(
            13,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )

        self.car_label = wx.StaticText(self, label="Select Car")
        self.car = wx.Choice(self, choices=build.get("car/cars"))
        self.car.SetSelection(0)

        self.logout = wx.Button(self, label="Log Out")

        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.sizer.Add(self.car_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.car, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.logout, 0, wx.LEFT | wx.RIGHT, 15)

        self.SetSizer(self.sizer)
        self.Layout()