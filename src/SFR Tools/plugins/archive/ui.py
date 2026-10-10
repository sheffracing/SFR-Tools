import wx
import wx.adv

from kipy import KiCad
from kipy.errors import ConnectionError as KiCadConnectionError
from urllib.parse import parse_qs
import json
from pathlib import Path
import requests
import traceback
import threading
import importlib
import time
import re

from utils.platform import win32
from utils.platform import darwin
from utils.log import log
from utils import settings, build

from typing_extensions import Literal

def get_theme_colours():
    """Return colours that adapt to light/dark mode."""
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
        img_path = (Path(__file__).parent / "icons" / path).absolute()
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
    def wrapper(self,*args,**kwargs):
        log("show dec")
        func(self,*args,**kwargs)
        log("show1")
        win32.attach_app(self, self.__foreground_hwnd, self.__board)
        darwin.attach_app(self)
        log("show2")
        self.CentreOnScreen()
        #del busy
        try:
            log("show3")
            result = self.ShowModal()
            self.Destroy()
            log("show4")
            return result
        except:
            self.Destroy()
    return wrapper

def app(func):
    def wrapper(self,*args,**kwargs):
        self.__foreground_hwnd = win32.prepare_app()
        self.__app = wx.App()
        darwin.prepare_app()
        #busy = wx.BusyCursor()
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
            log(f"App args: {' '.join(map(str, args))} kwargs: {' '.join(map(str, kwargs))} self: {self}")
            a = func(self,*args,**kwargs)
            log("app complete")
            return a
        except Exception as e:
            log(traceback.format_exc())
    return wrapper

def threaded(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(
            target=func,
            args=args,
            kwargs=kwargs
        )
        thread.start()
        return thread

    return wrapper

class CodeBox(wx.Panel):
    def __init__(self, parent, font, code, icon_path):
        super().__init__(parent)

        self.code = code
        self.font = font

        appearance = wx.SystemSettings.GetAppearance()
        dark_mode = appearance.IsDark()

        # Simplebook for swapping between text and icon
        self.book = wx.Simplebook(self)

        #
        # Text page
        #
        text_page = wx.Panel(self.book)

        self.text = wx.StaticText(
            text_page,
            label=code,
            style=wx.ALIGN_CENTER
        )
        self.text.SetFont(font)

        text_sizer = wx.BoxSizer(wx.VERTICAL)
        text_sizer.AddStretchSpacer(1)
        text_sizer.Add(self.text, 0, wx.ALIGN_CENTER | wx.TOP, 6)
        text_sizer.AddStretchSpacer(1)

        text_page.SetSizer(text_sizer)


        # Icon page
        icon_page = wx.Panel(self.book)

        self.icon_display = wx.StaticBitmap(
            icon_page,
            bitmap=load_icon(
                icon_path,
                dark_mode,
                (16, 18),
                False
            )
        )

        icon_sizer = wx.BoxSizer(wx.VERTICAL)
        icon_sizer.AddStretchSpacer(1)
        icon_sizer.Add(self.icon_display, 0, wx.ALIGN_CENTER)
        icon_sizer.AddStretchSpacer(1)

        icon_page.SetSizer(icon_sizer)

        #
        # Add pages
        #
        self.book.AddPage(text_page, "", True)   # Initially selected
        self.book.AddPage(icon_page, "")
        self.book.SetSelection(0)

        #
        # Main layout
        #
        text_size = self.text.GetBestSize()

        self.SetMinSize((
            text_size.width + 40,
            text_size.height + 20
        ))

        # Main layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(sizer)

        #
        # Click handlers
        #
        self.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.book.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.text.Bind(wx.EVT_LEFT_DOWN, self.copy_code)
        self.icon_display.Bind(wx.EVT_LEFT_DOWN, self.copy_code)

    def copy_code(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.code))
            wx.TheClipboard.Close()

        self.book.SetSelection(1)
        wx.CallLater(1000, self.restore)

    def restore(self):
        self.book.SetSelection(0)

    def set_code(self, code):
        """Update the displayed code and resize the control."""
        self.code = code
        self.text.SetLabel(code)

        self.text.InvalidateBestSize()
        self.text.GetParent().Layout()

        size = self.text.GetBestSize()
        self.SetMinSize((size.width + 40, size.height + 20))

        self.Layout()
        self.GetParent().Layout()

class PendingAuthPage(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        self.SetBackgroundColour(parent.colours["background"])

        self.title = wx.StaticText(self, label="Sign in to GitHub")
        self.title.SetFont(parent.title_font)
        self.title.SetForegroundColour(parent.colours["text"])
        self.description = wx.StaticText(self, label="Enter the code at GitHub")
        self.description.SetFont(parent.normal_font)
        self.description.SetForegroundColour(parent.colours["secondary"])
        self.code_box = CodeBox(self, parent.code_font ,parent.code,"copy.png")
        self.code_box.SetBackgroundColour(parent.colours["input"])
        self.code_box.SetForegroundColour(parent.colours["text"])
        self.open_button = wx.Button(self,label="Go to GitHub")
        self.open_button.SetFont(parent.normal_font)
        self.open_button.SetMinSize((120, 35))
        self.open_button.Bind(wx.EVT_BUTTON, parent.open_device_page)
        self.open_button.SetDefault()
        self.retry = wx.Button(self, label="Retry")
        self.retry.SetFont(parent.normal_font)
        self.retry.SetMinSize((120, 35))
        self.retry.Bind(wx.EVT_BUTTON, parent.on_retry)
        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(25)
        sizer.Add(self.title, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)
        sizer.Add(self.description, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.code_box, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        sizer.Add(self.open_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 8)
        sizer.Add(self.retry, 0, wx.ALIGN_CENTER | wx.BOTTOM, 25)
        self.SetSizer(sizer)

class FinishedAuthPage(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        self.SetBackgroundColour(parent.colours["background"])

        self.title = wx.StaticText(self, label="Success!")
        self.title.SetFont(parent.title_font)
        self.title.SetForegroundColour(parent.colours["text"])
        self.description = wx.StaticText(self, label="You have successfully logged in")
        self.description.SetFont(parent.normal_font)
        self.description.SetForegroundColour(parent.colours["secondary"])

        self.icon = wx.StaticBitmap(self, bitmap=load_icon("check.png", False, (96,96)))
        

        self.exit = wx.Button(self, wx.ID_OK, label="Done")
        self.exit.SetFont(parent.normal_font)
        self.exit.SetMinSize((120, 35))
        self.exit.SetDefault()
        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(25)
        sizer.Add(self.title, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)
        sizer.Add(self.description, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.exit, 0, wx.ALIGN_CENTER | wx.BOTTOM, 25)
        self.SetSizer(sizer)

class ErrorAuthPage(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        self.SetBackgroundColour(parent.colours["background"])

        self.title = wx.StaticText(self, label="Error")
        self.title.SetFont(parent.title_font)
        self.title.SetForegroundColour(parent.colours["text"])
        self.message = wx.StaticText(self, label="Unknown Error",style=wx.ALIGN_CENTER)
        self.message.SetFont(parent.verbatim_font)
        self.message.SetForegroundColour(parent.colours["secondary"])
        self.message.Wrap(300)
        self.description = wx.StaticText(self, label="You should contact the Extension Developer")
        self.description.SetFont(parent.normal_font)
        self.description.SetForegroundColour(parent.colours["secondary"])

        self.icon = wx.StaticBitmap(self, bitmap=load_icon("error.png", False, (96,96)))
        

        self.exit = wx.Button(self, label="Retry")
        self.exit.SetFont(parent.normal_font)
        self.exit.SetMinSize((120, 35))
        self.exit.SetDefault()
        self.exit.Bind(wx.EVT_BUTTON,self.on_exit)
        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(25)
        sizer.Add(self.title, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)
        sizer.Add(self.message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.description, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.exit, 0, wx.ALIGN_CENTER | wx.BOTTOM, 25)
        self.SetSizer(sizer)

        self.parent = parent
    def update(self,title: str, msg: str):
        self.title.SetLabelText("Error "+str(title))
        self.message.SetLabelText(str(msg))
        self.message.Wrap(300)
        self.Layout()
    def on_exit(self, Event):
        self.parent.pending_state = True
        self.parent.book.SetSelection(0)
        #self.parent.on_retry(None)
        #self.parent.init_poll()

class GithubAuthDialog(wx.Dialog):
    @app
    def __init__(self, parent, code, url, retry_callback, poll, error_callback):
        super().__init__(
            parent,
            title="GitHub Login",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        self.code = code
        self.url = url
        self.retry_callback = retry_callback
        self.error_callback = error_callback
        self.poll = poll

        self.pending_state = True
        self.error_state = False

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

        self.SetBackgroundColour(self.colours["background"])

        self.book = wx.Simplebook(self)
        self.pending = PendingAuthPage(self)
        self.finished = FinishedAuthPage(self)
        self.error = ErrorAuthPage(self)

        self.book.AddPage(self.pending,"Pending",True)
        self.book.AddPage(self.finished,"Finished",False)
        self.book.AddPage(self.error,"Error",False)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.book, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)

        self.SetMinSize((380, 300))
        self.CentreOnParent()


        #self.open_device_page(None)
        self.on_retry(None)
        self.init_poll()
    def open_device_page(self, event):
        wx.LaunchDefaultBrowser(self.url)
    def on_retry(self, event):
        # Call the supplied function
        self.pending.retry.Disable()
        new_code = self.retry_callback(self)
        self.disable_time = self.interval
        self.update_retry_text()

        if new_code:
            self.code = new_code
            self.pending.code_box.set_code(new_code)
    def update_retry_text(self):
        if self.disable_time > 0:
            self.pending.retry.SetLabel(
                f"Retry in {self.disable_time}s"
            )

            self.disable_time -= 1

            wx.CallLater(
                1000,
                self.update_retry_text
            )
        else:
            self.pending.retry.SetLabel("Retry")
            self.pending.retry.Enable()
    def init_poll(self):
        if not self.pending_state:
            return
        result = self.poll(self)
        if result:
            error_title, error_msg = self.error_callback(self)
            if error_title or error_msg:
                self.set_error(error_title,error_msg)
            else:
                self.pending_state = False
                self.book.SetSelection(1)
            #self.EndModal(wx.ID_OK)
            return
        wx.CallLater((self.interval or 10)*1000, self.init_poll)
    def set_error(self, title, message):
        self.pending_state = False
        self.error_state = True
        self.book.SetSelection(2)
        self.error.update(title,message)
    @show
    def show(self):
        pass


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, callbacks):
        super().__init__(
            parent,
            title="SFR Tools Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.callback = callbacks

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

        panel = wx.Panel(self)

        title = wx.StaticText(panel, label="Settings")
        title.SetFont(self.title_font)

        cars: list = settings.get("info/car/cars")
        current_car = settings.get("info/car") if  "current" in settings.get("info/car") and settings.get("info/car") else build.get("info/cars")[0]
        if not current_car in cars:
            cars.insert(0,current_car)
        try:
            index = cars.index(current_car)
        except ValueError:
            index = 0

        car_label = wx.StaticText(panel, label="Select SFR Car")
        car = wx.Choice(panel, choices=cars)
        car.SetSelection(index)
        car.Bind(wx.EVT_CHOICE,lambda e: self.callback["car"](self,e))

        logout = wx.Button(panel, wx.ID_CLOSE, "Logout")
        logout.Bind(wx.EVT_BUTTON, lambda e: self.callback["logout"](self, e))
        
        close = wx.Button(panel, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        close.SetDefault()

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title, 0, wx.ALL, 15)
        sizer.Add(car_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(car, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.Add(logout, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        sizer.SetMinSize(300,100)
        sizer.Fit(panel)

        self.Fit()


class BranchDropdown(wx.PopupWindow):
    def __init__(self, parent):
        super().__init__(parent, flags=wx.BORDER_SIMPLE)

        self.panel = wx.Panel(self)

        title = wx.StaticText(self.panel, label="Advanced Settings")
        title.SetFont(parent.title_font)

        branch_label = wx.StaticText(self.panel, label="Select User Branch to pull")

        parent.branches = parent.callback["get_branches"](parent, parent.current_board)
        parent.current_branch = parent.branches[0] if len(parent.branches) > 0 else None

        self.branch = wx.Choice(self.panel, choices=parent.branches)
        self.branch.SetSelection(0)
        self.branch.Bind(wx.EVT_CHOICE, self.update_commits)

        parent.commits = parent.callback["get_commits"](parent, parent.current_branch)
        parent.current_commit = parent.commits[0] if len(parent.commits) > 0 else None

        commit_label = wx.StaticText(self.panel, label="Select Branch Commit to pull")
        #branch_label.SetFont(self.normal_font)
        self.commit = wx.Choice(self.panel, choices=parent.commits)
        self.commit.SetSelection(0)
        self.commit.Bind(wx.EVT_CHOICE, lambda e: self.set_commit(e))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title, 0, wx.ALL, 15)
        sizer.Add(branch_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.branch, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.Add(commit_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.commit, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.panel.SetSizer(sizer)
        self.SetSize((300, 100))

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)

        self.parent = parent
        self.Bind(wx.EVT_ACTIVATE, self.on_focus)
    def on_focus(self, event):
        if not event.GetActive():
            def clear():
                self.parent.advanced_dropdown = None
            wx.CallLater(millis=200,callableObj=clear)
            self.parent.advanced_dropdown = True
            self.Destroy()
    def update_branches(self, branches):
        self.branch.SetItems(branches)
        self.branch.SetSelection(0)
    def update_commits(self, event):
        choice = event.GetEventObject()
        self.parent.current_branch = choice.GetStringSelection()
        self.parent.commits = self.parent.callback["get_commits"](self.parent, self.parent.current_branch)

        self.commit.SetItems(self.parent.commits)
        self.commit.SetSelection(0)
    def set_commit(self, event):
        choice = event.GetEventObject()
        self.parent.current_commit = choice.GetStringSelection()




class DownloadDialog(wx.Dialog):
    def __init__(self, parent, callbacks, data):
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.callback = callbacks

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

        panel = wx.Panel(self)

        self.parent = parent
        self.data = data
        self.advanced_showing = False
        git = self.parent.git

        title = wx.StaticText(panel, label="Download PCB from GitHub")
        title.SetFont(self.title_font)

        board_label = wx.StaticText(panel, label="Select Board")

        self.boards = self.data["boards"]
        self.current_board = self.boards[0] if len(self.boards) > 0 else None

        self.branches = ["main"]
        self.current_branch = "main"

        self.commits = []
        self.current_commit = None

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
        

        pull = wx.Button(panel, label="Pull PCB")
        pull.Bind(wx.EVT_BUTTON, lambda e: self.callback["pull"](self,e))
    
        close = wx.Button(panel, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        close.SetDefault()

        self.branch_label.Hide()
        self.branch.Hide()
        self.commit_label.Hide()
        self.commit.Hide()
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.sizer.Add(title, 0, wx.ALL, 15)
        self.sizer.Add(board_label, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.board, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.branch_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.sizer.Add(self.branch, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.commit_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.sizer.Add(self.commit, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.sizer.Add(self.advanced, 0, wx.LEFT | wx.RIGHT, 15)
        self.sizer.AddSpacer(15)
        self.sizer.Add(pull, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(self.sizer)
        self.sizer.SetMinSize(300,50)
        self.sizer.Fit(panel)

        self.Fit()
        

    def on_advanced(self, event):
        try:
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
        except Exception as e:
            log(traceback.format_exc())

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

    def on_commit_update(self, event):
        choice = event.GetEventObject()
        self.current_commit = choice.GetStringSelection()

class PlaceholderTextCtrl(wx.TextCtrl):
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

class SaveDialog(wx.Dialog):
    def __init__(self, parent, callbacks):
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.callback = callbacks

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

        panel = wx.Panel(self)

        self.parent = parent
        self.fufilled = False

        title = wx.StaticText(panel, label="Save to GitHub")
        title.SetFont(self.title_font)

        commit_label = wx.StaticText(panel, label="Summary of changes")

        self.summary = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.summary.SetHint("Short summary of your changes.")
        self.summary.Bind(wx.EVT_KILL_FOCUS, self.on_summary)

        self.description = PlaceholderTextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, placeholder="Describe your changes (optional)")
        self.description.SetMinSize((-1, self.description.GetCharHeight() * 4))

        self.error = wx.StaticText(panel, label="This question is required")
        self.error.SetForegroundColour(wx.RED)
        wx.CallLater(1, self.error.Hide)

        save = wx.Button(panel, label="Save")
        save.Bind(wx.EVT_BUTTON, lambda e: self.try_exit(self))
        save.SetDefault()

        close = wx.Button(panel, wx.ID_CLOSE, "Cancel")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title, 0, wx.ALL, 15)
        sizer.Add(commit_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.summary, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.AddSpacer(15)
        sizer.Add(save, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        sizer.SetMinSize(300,100)
        sizer.Fit(panel)

        self.Fit()

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
    def try_exit(self, event):
        self.on_summary(None)
        if not self.fufilled:
            return
        success, data = self.callback["success"](self, self.summary.GetValue(), self.description.GetValue())
        if not success:
            self.on_error(data)
        else:
            self.EndModal(wx.ID_SAVE)
    def on_error(self, data):
        try:
            self.fufilled = False
            self.error.SetLabelText(str(data["error"]))
            self.error.Show()
            self.error.GetParent().Layout()
            self.error.Fit()
            self.error.Refresh()
        except Exception as e:
            log(traceback.format_exc())




class ReviewDialog(wx.Dialog):
    def __init__(self, parent, callbacks):
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.callback = callbacks

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

        panel = wx.Panel(self)

        self.parent = parent
        self.fufilled = False

        title = wx.StaticText(panel, label="Send PCB for review")
        title.SetFont(self.title_font)

        desc_label = wx.StaticText(panel, label="Description of Board & Changes")
        self.description = PlaceholderTextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, placeholder="Describe the board and/or changes you have made.\n You can come back and edit the request on Github later.")
        self.description.SetMinSize((-1, self.description.GetCharHeight() * 4))
        self.description.Bind(wx.EVT_KILL_FOCUS, self.on_desc)

        self.error = wx.StaticText(panel, label="This question is required")
        self.error.SetForegroundColour(wx.RED)
        wx.CallLater(1, self.error.Hide)

        request = wx.Button(panel, label="Request Review")
        request.Bind(wx.EVT_BUTTON, lambda e: self.try_exit(self))
        request.SetDefault()

        close = wx.Button(panel, wx.ID_CLOSE, "Cancel")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title, 0, wx.ALL, 15)
        sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.AddSpacer(15)
        sizer.Add(request, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        sizer.SetMinSize(300,100)
        sizer.Fit(panel)

        self.Fit()

    def on_desc(self, event):
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
    def try_exit(self, event):
        self.on_desc(None)
        if not self.fufilled:
            return
        self.callback["success"](self, self.description.GetValue())

class FileDrop(wx.FileDropTarget):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    def OnDropFiles(self, x: int = None, y: int = None, files: list[str] = []):
        return self.callback(files)

class DragDrop(wx.Panel):
    def __init__(self, parent, panel, text: str, callback):
        super().__init__(
            panel,
            style=wx.BORDER_SIMPLE
            )

        self.parent = parent
        self.panel = panel

        theme_colours = get_theme_colours()
        self.SetBackgroundColour(theme_colours["background"])

        self.target = FileDrop(lambda x, y, files: callback(parent,files))
        self.SetDropTarget(self.target)

        self.desc = wx.StaticText(self, label=text)
        self.icon = wx.StaticBitmap(self, bitmap=load_icon("download.png", False, (40,40)))


        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.desc, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.SetSizer(sizer)

class LinkFile(wx.Panel):
    def __init__(self, parent, panel, text: str, callback):
        super().__init__(
            panel,
            style=wx.BORDER_SIMPLE
            )

        self.parent = parent
        self.panel = panel

        theme_colours = get_theme_colours()
        self.SetBackgroundColour(theme_colours["background"])

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.desc, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.SetSizer(sizer)

class ComponentDialog(wx.Dialog):
    def __init__(self, parent, callbacks):
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.callback = callbacks

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

        panel = wx.Panel(self)

        self.parent = parent
        self.fufilled = False

        title = wx.StaticText(panel, label="Add a component to a library")
        title.SetFont(self.title_font)

        desc_label = wx.StaticText(panel, label="Drag && Drop a Footprint or Symbol")
        self.dragbox_sym = DragDrop(self, panel, "Add Symbol", self.onSymDrop)

        self.foot_mode = wx.Choice(panel, choices=["Add new Footprint", "Link existing Footprint"])
        self.add_foot = wx.Panel(panel)
        self.dragbox_foot = DragDrop(self, self.add_foot, "Add Footprint", self.onSymDrop)

        self.link_foot = wx.Panel(panel)
        self.select_foot = wx.Choice(self.link_foot,choices=["0805_Resistor","0605_Capacitor"])

        self.foot_book = wx.Simplebook(panel)
        self.foot_book.AddPage(self.add_foot,"Add",True)
        self.foot_book.AddPage(self.link_foot,"Link",True)

        self.description = PlaceholderTextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, placeholder="Describe the board and/or changes you have made.\n You can come back and edit the request on Github later.")
        self.description.SetMinSize((-1, self.description.GetCharHeight() * 4))
        self.description.Bind(wx.EVT_KILL_FOCUS, self.on_desc)

        self.error = wx.StaticText(panel, label="This question is required")
        self.error.SetForegroundColour(wx.RED)
        wx.CallLater(1, self.error.Hide)

        request = wx.Button(panel, label="Request Review")
        request.Bind(wx.EVT_BUTTON, lambda e: self.try_exit(self))
        request.SetDefault()

        close = wx.Button(panel, wx.ID_CLOSE, "Cancel")
        close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title, 0, wx.ALL, 15)
        sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.dragbox_sym, 0, wx.EXPAND | wx.ALL, 15)
        sizer.Add(self.foot_mode, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.foot_book, 0, wx.EXPAND | wx.ALL, 15)
        sizer.AddSpacer(10)
        sizer.Add(self.description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        sizer.Add(self.error, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.AddSpacer(15)
        sizer.Add(request, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(close, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        sizer.SetMinSize(300,100)
        sizer.Fit(panel)

        self.Fit()

    def on_desc(self, event):
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

    def onSymDrop(self, files: list[str] = []):
        for raw_path in files:
            path = Path(raw_path)
            is_sym, msg = self.parent.plugin.is_file_symbol(path)
            log(f"{is_sym}, {msg}")

    def try_exit(self, event):
        self.on_desc(None)
        if not self.fufilled:
            return
        self.callback["success"](self, self.description.GetValue())

class MainMenu(wx.Dialog):
    @app
    def __init__(self, parent, tools, git, plugin):
        log("STARTING MENU")
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        log("starting menu now")
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
        self.colours = get_theme_colours()
        self.appearance = wx.SystemSettings.GetAppearance()
        self.dark_mode = self.appearance.IsDark()
        self.git = git
        self.plugin = plugin

        icon = wx.Icon()
        icon.CopyFromBitmap(load_icon("icon.png",self.dark_mode, (24,24)))
        self.SetIcon(icon)
        self.SetBackgroundColour(self.colours["background"])

        self.panel = wx.Panel(self)
        wx.ToolTip.SetDelay(300)

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.tools = {}
        for priority, identifier in enumerate(tools):
            data = tools[identifier]
            log(f"data: {data}")
            try:
                package = importlib.import_module("flow."+data["package"])
            except Exception as e:
                ui = InfoDialog(None, "An Exception has occured", str(e), "Error")
                ui.show()
                wx.CallLater(1, self.EndModal, wx.ID_CANCEL)
            tool = wx.BitmapButton(self.panel, bitmap=load_icon(data["icon"],self.dark_mode,(24,24)),size=(40,40))
            tool.SetToolTip(data["tooltip"])
            tool.Bind(wx.EVT_BUTTON, lambda e, package=package: package.get(self))
            sizer.Add(tool, 0, wx.TOP | wx.LEFT | wx.BOTTOM, 20)
            self.tools[identifier] = tool

        sizer.AddSpacer(20)
        self.panel.SetSizer(sizer)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)

        self.SetMinSize((380, 300))
        self.CentreOnParent()
    @show
    def show(self):
        pass


class InfoPage(wx.Panel):
    def __init__(self, parent, title: str = "Information", message: str = "Unknown", detail: str = None, icon: str = "info.png", retry: bool = False):
        super().__init__(parent)

        self.parent = parent

        title_font = wx.Font(
            16,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD
        )

        normal_font = wx.Font(
            14,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL
        )

        verbatim_font = wx.Font(
            14,
            wx.FONTFAMILY_TELETYPE,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD
        )
        theme_colours = get_theme_colours()


        self.SetBackgroundColour(theme_colours["background"])

        self.title = wx.StaticText(self, label=title)
        self.title.SetFont(title_font)
        self.title.SetForegroundColour(theme_colours["text"])

        self.detail = wx.StaticText(self, label=detail or "Unknown", style=wx.ALIGN_CENTER)
        self.detail.SetFont(verbatim_font)
        self.detail.SetForegroundColour(theme_colours["secondary"])
        self.detail.Wrap(220)

        if not detail:
            self.detail.Hide()

        self.message = wx.StaticText(self, label=message, style=wx.ALIGN_CENTER)
        self.message.SetFont(normal_font)
        self.message.SetForegroundColour(theme_colours["secondary"])
        self.message.Wrap(220)

        self.icon = wx.StaticBitmap(self, bitmap=load_icon(icon, False, (96,96)))

        self.retry = wx.Button(self, label="Retry")
        self.retry.SetFont(normal_font)
        self.retry.SetMinSize((120, 35))
        self.retry.Bind(wx.EVT_BUTTON, self.on_retry)

        if not retry:
            self.retry.Hide()
        
        self.exit = wx.Button(self, label="Close")
        self.exit.SetFont(normal_font)
        self.exit.SetMinSize((120, 35))
        self.exit.SetDefault()
        self.exit.Bind(wx.EVT_BUTTON,self.on_close)

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(25)
        sizer.Add(self.title, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)
        sizer.Add(self.detail, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        sizer.AddSpacer(10)
        sizer.Add(self.message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 36)
        sizer.Add(self.icon, 0, wx.ALIGN_CENTER | wx.ALL, 25)
        sizer.Add(self.retry, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        sizer.Add(self.exit, 0, wx.ALIGN_CENTER | wx.BOTTOM, 25)
        self.SetSizer(sizer)
        self.Layout()

        required_height = self.GetSizer().CalcMin()[1]

        self.parent.SetClientSize(
            self.parent.GetClientSize().width,
            required_height
        )

        self.parent.Layout()

    def on_close(self, event):
        self.parent.EndModal(wx.ID_CLOSE)
    def on_retry(self, event):
        self.parent.EndModal(wx.ID_RETRY)
    def change(self, title, message, detail, icon, retry):
        self.title.SetLabelText(title)
        self.message.SetLabelText(message)
        self.message.Wrap(220)
        self.detail.SetLabelText(detail or "Unknown")
        self.detail.Wrap(220)
        self.icon.SetBitmap(load_icon(icon, False, (96,96)))
        self.detail.Show(bool(detail))
        self.retry.Show(bool(retry))

        self.Layout()

        required_height = self.GetSizer().CalcMin()[1]

        client_width, _ = self.parent.GetClientSize()

        self.parent.SetClientSize(
            client_width,
            required_height
        )

        self.parent.Layout()


class InfoDialog(wx.Dialog):
    @app
    def __init__(self, parent, title: str, message: str, dialogType: Literal["Info", "Loading", "Success", "Error"] = "Info", retry: bool = False, poll = None):
        super().__init__(
            parent,
            title="SFR Tools",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        log(f"Title: {title}, 'Message: {message}, Type: {dialogType}")
        theme_colours = get_theme_colours()
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
        self.retry = retry
        self.poll = poll
        self.type = dialogType

        self.SetBackgroundColour(theme_colours["background"])

        self.book = wx.Simplebook(self)
        self.page = InfoPage(self, self.title, self.message, self.detail, self.icon, self.retry)

        self.book.AddPage(self.page,"Info",True)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(outer)
        self.SetMinSize((300, 300))
        self.SetSize(self.GetBestSize())
        self.Layout()

        if self.poll:# and self.type == "Loading":
            self.init_poll()
    def init_poll(self):
        #if self.type != "Loading":
        #    return
        result, data = self.poll(self)
        if result:
            self.type = data["dialogType"]
            self.title = data["title"]
            self.message = data["message"] if self.type != "Error" else "You should contact the Extension Developer."
            self.detail = data["message"] if self.type == "Error" else None
            try:
                self.icon = self.icons[self.type]
            except KeyError:
                self.icon = self.icons["Info"]
            self.retry = data["retry"]
            self.page.change(self.title, self.message, self.detail, self.icon, self.retry)
        wx.CallLater(1000, self.init_poll)
    @show
    def show(self):
        pass