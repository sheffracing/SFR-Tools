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


class DownloadDialog(wx.Dialog, UIUtils.Worker, UIUtils.Constructor):
    def __init__(self, parent, callbacks, data):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Worker.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)

        self.callback = callbacks
        self.data = data
        self.advanced_showing = False

        self.boards = self.data["boards"]
        self.branches = ["main"]
        self.commits = []

        self.current_board = self.boards[0] if len(self.boards) > 0 else None
        self.current_branch = "main"
        self.current_commit = None

        panel = wx.Panel(self)

        self.title = wx.StaticText(panel, label="Download PCB from GitHub")
        self.title.SetFont(self.title_font)

        self.board_label = wx.StaticText(panel, label="Select Board")
        self.board = wx.Choice(panel, choices=self.boards)
        self.board.SetSelection(0)
        self.board.Bind(wx.EVT_CHOICE, self.on_board_update)

        self.advanced = wx.Button(panel, label="Advanced")
        self.advanced.Bind(wx.EVT_BUTTON, self.on_advanced)

        self.branch_label = wx.StaticText(panel, label="Select Branch")
        self.branch = wx.Choice(panel, choices=self.branches)
        self.branch.SetSelection(0)
        self.branch.Bind(wx.EVT_CHOICE, self.on_branch_update)
        
        self.commit_label = wx.StaticText(panel, label="Select Commit (optional)")
        self.commit = wx.Choice(panel, choices=self.commits)
        self.commit.SetSelection(0)
        self.commit.Bind(wx.EVT_CHOICE, self.on_commit_update)
        

        self.pull = wx.Button(panel, label="Pull PCB")
        self.pull.Bind(wx.EVT_BUTTON, lambda e: self.callback["pull"](self,e))

        self.close = wx.Button(panel, wx.ID_CLOSE, "Close")
        self.close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        self.close.SetDefault()

        self.branch_label.Hide()
        self.branch.Hide()
        self.commit_label.Hide()
        self.commit.Hide()
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.sizer.Add(self.title, 0, wx.ALL, 15)
        self.sizer.Add(self.board_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.board, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.branch_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.sizer.Add(self.branch, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.commit_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.sizer.Add(self.commit, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.advanced, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(15)
        self.sizer.Add(self.pull, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(self.close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,50)
        self.sizer.Fit(panel)

        self.Fit()
        
    @misc.handle
    def on_advanced(self, event):
        self.advanced_showing = not self.advanced_showing
        self.on_board_update(None, self.current_board)
        self.on_branch_update(None,self.current_branch)

        self.branch_label.Show(self.advanced_showing)
        self.branch.Show(self.advanced_showing)
        self.commit_label.Show(self.advanced_showing)
        self.commit.Show(self.advanced_showing)

        self.sizer.Layout()
        self.Fit()
        self.sizer.SetSizeHints(self)
        self.Layout()

    @misc.handle
    def on_board_update(self, event, board: str = None):
        if board:
            self.current_board = board
        else:
            choice = event.GetEventObject()
            self.current_board = choice.GetStringSelection()

        self.branches: list = self.callback["get_branches"](self, self.current_board)
        self.branch.SetItems(self.branches)
        try:
            main = self.branches.index("main")
            self.branch.SetSelection(main)
            self.current_branch = self.branches[main]
        except:
            self.branch.SetSelection(0)
            self.current_branch = self.branches[0]

    @misc.handle
    def on_branch_update(self, event, branch: str = None):
        if branch:
            self.current_branch = branch
        else:
            choice = event.GetEventObject()
            self.current_branch = choice.GetStringSelection()

        self.commits: list = self.callback["get_commits"](self, self.current_branch)
        self.commit.SetItems(self.commits)
        self.commit.SetSelection(0)
        self.current_commit = self.commits[0] if len(self.commits) > 0 else None

    @misc.handle
    def on_commit_update(self, event):
        choice = event.GetEventObject()
        self.current_commit = choice.GetStringSelection()