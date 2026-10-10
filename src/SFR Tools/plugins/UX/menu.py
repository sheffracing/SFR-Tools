import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback
import importlib

from utils.platform import win32
from utils.platform import darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils
from UX.info import InfoDialog

class MainMenu(wx.Dialog, UIUtils.Entrypoint, UIUtils.Constructor):

    @misc.handle
    def __init__(self, parent, tools, git, plugin):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Entrypoint.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)

        self.git = git
        self.plugin = plugin

        self.panel = wx.Panel(self)
        wx.ToolTip.SetDelay(300)

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.tools = {}
        for priority, identifier in enumerate(tools):
            data = tools[identifier]
            #if not data["enabled"]:
            #    continue
            try:
                package = importlib.import_module("flow."+data["package"])
            except Exception as e:
                ui = InfoDialog(None, "An Exception has occured", str(e), "Error")
                ui.show()
                wx.CallLater(1, self.EndModal, wx.ID_CANCEL)
            tool = wx.BitmapButton(self.panel, bitmap=UIUtils.load_icon(data["icon"],self.dark_mode,(24,24)),size=(40,40))
            tool.SetToolTip(data["tooltip"])
            tool.SetBackgroundColour(self.colours["secondary"])
            tool.Enable(data["enabled"])
            tool.Bind(wx.EVT_BUTTON, lambda e, package=package: package.get(self))
            self.sizer.Add(tool, 0, wx.TOP | wx.LEFT | wx.BOTTOM, 20)
            self.tools[identifier] = tool

        self.sizer.AddSpacer(20)
        self.panel.SetSizer(self.sizer)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)

        self.SetMinSize((380, 300))
        self.CentreOnParent()