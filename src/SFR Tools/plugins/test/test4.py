from UX.info import InfoDialog

ui = InfoDialog(None, "An exception has occured", """Recieved error Traceback (most recent call last):
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/action.py", line 27, in <module>
    from flow import menu, login, autosave
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/flow/menu.py", line 9, in <module>
    from UX.menu import MainMenu
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/UX/menu.py", line 15, in <module>
    from ui import InfoDialog
ModuleNotFoundError: No module named 'ui'

Recieved error Traceback (most recent call last):
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/action.py", line 27, in <module>
    from flow import menu, login, autosave
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/flow/menu.py", line 9, in <module>
    from UX.menu import MainMenu
  File "/Users/joseph/Documents/KiCad/10.0/3rdparty/plugins/com_github_sheffracing_SFR-Tools/UX/menu.py", line 15, in <module>
    from ui import InfoDialog
ModuleNotFoundError: No module named 'ui'
""", "Error")
ui.ShowModal()

ui = InfoDialog(None, "Success!", "yay", "Success")
ui.ShowModal()

ui = InfoDialog(None, "An exception has occured", """Recieved error Traceback (most recent call last):
ModuleNotFoundError: No module named 'ui'
""", "Error")
ui.ShowModal()