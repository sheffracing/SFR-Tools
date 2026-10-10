import wx
import wx.adv

from urllib.parse import parse_qs
from pathlib import Path
import traceback
import threading
import importlib
from typing_extensions import Literal
import time
import textwrap

from utils.platform import win32, darwin
from utils.log import log
from utils import settings, build, misc
from utils import ui as UIUtils

INFO_DIALOG_MIN_WIDTH = 300
INFO_DIALOG_MAX_WIDTH = 520
INFO_DIALOG_SCREEN_HEIGHT_RATIO = 0.8


class InfoDialog(wx.Dialog, UIUtils.Worker, UIUtils.Constructor):
    @misc.lite
    @UIUtils.app
    def __init__(self, parent, title: str, message: str, dialogType: Literal["Info", "Loading", "Success", "Error"] = "Info", buttons: list[str] = [("Close", wx.ID_CLOSE)]):
        wx.Dialog.__init__(
            self,
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        )
        UIUtils.Worker.__init__(self, parent)
        UIUtils.Constructor.__init__(self, parent)
        
        self.icons = {
            "Info": "info.png",
            "Loading": "loading.png",
            "Success": "check.png",
            "Error": "error.png"
        }

        self.title = title
        self.message = message if dialogType != "Error" else "You should contact the Extension Developer."
        self.detail = message if dialogType == "Error" else None

        try:
            self.icon = self.icons[dialogType]
        except KeyError:
            self.icon = self.icons["Info"]

        self.buttons = buttons
        self.type = dialogType

        self.book = wx.Simplebook(self)
        self.page = InfoPage(self, self.title, self.message, self.detail, self.icon, self.buttons)

        self.book.AddPage(self.page,"Info",True)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(self.sizer)
        self.Fit()
        self.SetMinSize((300, 300))
        self.SetMaxSize((INFO_DIALOG_MAX_WIDTH, -1))
        fitted_size = self.GetSize()
        self.SetSize((min(fitted_size.width, INFO_DIALOG_MAX_WIDTH), fitted_size.height))
        self.page.resize_to_content()

    @misc.lite
    def update(self, title: str, message: str, dialogType: Literal["Info", "Loading", "Success", "Error"] = "Info", buttons: list[tuple[str, int]] = [("Close", wx.ID_CLOSE)]):
        self.title = title
        self.message = message if dialogType != "Error" else "You should contact the Extension Developer."
        self.detail = message if dialogType == "Error" else None
        self.type = dialogType
        self.buttons = buttons

        try:
            self.icon = self.icons[dialogType]
        except KeyError:
            self.icon = self.icons["Info"]

        self.page.change(self.title, self.message, self.detail, self.icon, self.buttons)

class InfoPage(wx.Panel, UIUtils.Constructor):
    @misc.lite
    def __init__(self, parent, title: str = "Information", message: str = "Unknown", detail: str = None, icon: str = "info.png", buttons: list[str] = [("Close", wx.ID_CLOSE)]):
        wx.Panel.__init__(
                    self,
                    parent
        )
        UIUtils.Constructor.__init__(self, parent)

        self.parent = parent
        self.Buttons = {}

        self.title = wx.StaticText(self, label=title, style=wx.ALIGN_CENTER)
        self.title.SetFont(self.title_font)
        self.title.SetForegroundColour(self.colours["text"])
        self.wrap_label(self.title)

        self.detail_view = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.detail_view.SetBackgroundColour(self.colours["background"])
        # Pixel scroll units let mouse and trackpad wheel events move smoothly.
        self.detail_view.SetScrollRate(0, 1)
        self._detail_wheel_remainder = 0.0
        self.detail = wx.TextCtrl(
            self.detail_view,
            value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL | wx.BORDER_NONE,
        )
        self.detail.SetFont(self.verbatim_font)
        self.detail.SetForegroundColour(self.colours["text"])
        self.detail.SetBackgroundColour(self.colours["background"])
        self.detail.Bind(wx.EVT_MOUSEWHEEL, self.on_detail_mousewheel)
        self.detail_view.Bind(wx.EVT_MOUSEWHEEL, self.on_detail_mousewheel)
        if detail:
            self.set_detail(detail)
        self.detail_sizer = wx.BoxSizer(wx.VERTICAL)
        self.detail_sizer.Add(self.detail, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        self.detail_view.SetSizer(self.detail_sizer)
        self.detail_sizer.Layout()
        self.detail_view.FitInside()

        if not detail:
            self.detail_view.Hide()

        self.message = wx.StaticText(self, label=message, style=wx.ALIGN_CENTER)
        self.message.SetFont(self.normal_font)
        self.message.SetForegroundColour(self.colours["secondary"])
        self.wrap_label(self.message)

        self.icon = wx.StaticBitmap(self, bitmap=UIUtils.load_icon(icon, False, (96,96)))

        self.button_sizer = wx.BoxSizer(wx.VERTICAL)
        self.generate_buttons(buttons)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.AddSpacer(25)
        self.sizer.Add(self.title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        self.sizer.AddSpacer(12)
        # Let the detail viewport absorb available height so the fixed
        # message, icon, and buttons retain their space at the bottom.
        self.sizer.Add(self.detail_view, 1, wx.EXPAND)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        self.sizer.Add(self.icon, 0, wx.ALIGN_CENTER | wx.ALL, 25)

        self.sizer.Add(self.button_sizer, 0, wx.EXPAND)

        self.sizer.AddSpacer(20)
        self.SetSizer(self.sizer)
        self.Layout()
        self.detail_view.SetMinSize((-1, self.detail_sizer.CalcMin().height))

    @staticmethod
    def wrap_label(label, width=220):
        # Clear dimensions cached for a previous value, wrap, then reserve a
        # height measured from the actual lines rather than wx's cached size.
        label.SetMinSize(wx.DefaultSize)
        label.Wrap(width)
        dc = wx.ClientDC(label)
        dc.SetFont(label.GetFont())
        line_height = dc.GetTextExtent("Mg")[1]
        lines = label.GetLabelText().splitlines() or [""]
        columns = max(width // max(dc.GetTextExtent("M")[0], 1), 1)
        rendered_height = sum(
            max(1, (len(line) + columns - 1) // columns) * line_height
            for line in lines
        )
        label.InvalidateBestSize()
        label.SetMinSize((-1, max(label.GetBestSize().height, rendered_height)))
    @misc.lite
    def format_detail(self, detail, width=220):
        """Insert explicit line breaks so wx measures long detail text reliably."""
        dc = wx.ClientDC(self)
        dc.SetFont(self.verbatim_font)
        char_width = max(dc.GetTextExtent("M")[0], 1)
        columns = max(width // char_width, 1)
        lines = []
        for paragraph in detail.splitlines() or [""]:
            lines.extend(textwrap.wrap(
                paragraph,
                width=columns,
                break_long_words=True,
                break_on_hyphens=False,
                replace_whitespace=False,
                drop_whitespace=True,
            ) or [""])
        return "\n".join(lines)

    @misc.lite
    def set_detail(self, detail):
        formatted = self.format_detail(detail) if detail else "Unknown"
        self.detail.SetValue(formatted)
        self.detail.SetInsertionPoint(0)
        dc = wx.ClientDC(self.detail_view)
        dc.SetFont(self.verbatim_font)
        line_height = dc.GetTextExtent("Mg")[1]
        line_count = max(1, len(formatted.splitlines()))
        self.detail.SetMinSize((-1, line_count * line_height + 8))
        self.detail.InvalidateBestSize()

    def on_detail_mousewheel(self, event):
        rotation = event.GetWheelRotation()
        delta = event.GetWheelDelta() or 120
        lines = event.GetLinesPerAction() or 3
        if not rotation:
            return

        line_height = max(self.detail.GetCharHeight(), 1)
        pixel_delta = -(rotation / delta) * lines * line_height + self._detail_wheel_remainder
        movement = int(pixel_delta)
        self._detail_wheel_remainder = pixel_delta - movement
        view_x, view_y = self.detail_view.GetViewStart()
        self.detail_view.Scroll(view_x, max(0, view_y + movement))
    
    @misc.lite
    def resize_to_content(self):
        # Measure the full detail before deciding whether it needs a scroll
        # viewport. Resetting the viewport minimum avoids carrying forward a
        # previous capped size when the dialog is updated with shorter text.
        self.detail_view.SetMinSize(wx.DefaultSize)
        self.detail_view.SetMaxSize(wx.DefaultSize)
        self.detail_sizer.Layout()
        detail_size = self.detail_sizer.CalcMin()
        self.detail_view.FitInside()
        # Restore the complete detail height for measuring the natural page
        # size. Without this, CalcMin sees only the scroll window's tiny
        # default size and may allocate just one text line to the viewport.
        self.detail_view.SetMinSize((-1, detail_size.height))
        self.Layout()
        self.sizer.Layout()
        required_size = self.sizer.CalcMin()
        display_index = wx.Display.GetFromWindow(self.parent)
        screen_height = (
            wx.GetDisplaySize().height
            if display_index == wx.NOT_FOUND
            else wx.Display(display_index).GetClientArea().height
        )
        height_limit = max(300, int(screen_height * INFO_DIALOG_SCREEN_HEIGHT_RATIO))
        required_height = max(required_size.height, 300)
        if self.detail_view.IsShown() and required_height > height_limit:
            non_detail_height = required_height - detail_size.height
            detail_view_height = max(1, height_limit - non_detail_height)
            self.detail_view.SetMinSize((-1, detail_view_height))
            required_height = height_limit
        else:
            self.detail_view.SetMinSize((-1, detail_size.height))
            self.detail_view.SetMaxSize(wx.DefaultSize)
        self.Layout()
        self.sizer.Layout()
        before = self.parent.GetClientSize()
        client_width = min(max(before.width, INFO_DIALOG_MIN_WIDTH), INFO_DIALOG_MAX_WIDTH)
        # Simplebook can keep its initial minimum after the page changes.
        # Replace that minimum with the page's newly measured size so the
        # dialog's outer sizer has a height to expand to.
        self.parent.book.SetMinSize(wx.DefaultSize)
        self.parent.book.SetMinSize((min(max(required_size.width, 300), INFO_DIALOG_MAX_WIDTH), required_height))
        self.parent.book.InvalidateBestSize()
        self.parent.sizer.Layout()
        self.parent.SetClientSize((client_width, required_height))
        self.parent.Layout()
        after = self.parent.GetClientSize()
       
    @misc.lite
    def generate_buttons(self, buttons):
        self.button_sizer.Clear(delete_windows=False)
        n = 0
        for label, data in self.Buttons.items():
            button, msg = data[0], data[1]
            self.button_sizer.Detach(button)
            button.Destroy()


        self.Buttons = {}
        for data in buttons:
            label, msg = data
            button = wx.Button(self, label=label)
            button.SetFont(self.normal_font)
            button.SetMinSize((120, 35))
            button.Bind(wx.EVT_BUTTON, lambda event, x=msg: self.on_button(x,event))
            self.button_sizer.Add(button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

            self.Buttons[label] = [button, msg]
            if n == 0:
                button.SetDefault()
            n += 1
        self.button_sizer.Layout()

    @misc.lite
    def on_button(self, message: int, event):
        self.parent.EndModal(message)
        
    @misc.lite
    def change(self, title, message, detail, icon, buttons):
        self.title.SetLabelText(title)
        self.title.InvalidateBestSize()
        self.wrap_label(self.title)

        self.message.SetLabelText(message)
        self.message.InvalidateBestSize()
        self.wrap_label(self.message)

        self.set_detail(detail)

        self.icon.SetBitmap(UIUtils.load_icon(icon, False, (96,96)))
        self.detail.Show(bool(detail))
        self.detail_view.Show(bool(detail))
        self.detail.GetParent().Layout()
        self.detail_sizer.Layout()
        self.detail_view.FitInside()
        self.detail_view.Scroll(0, 0)

        self.generate_buttons(buttons)

        self.sizer.Layout()
        self.Layout()
        # Let wx finish updating wrapped StaticText best sizes before fitting.
        wx.CallAfter(self.resize_to_content)
