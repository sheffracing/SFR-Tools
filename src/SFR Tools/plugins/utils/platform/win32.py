# macOS dialog integration for Stage Manager.
#
# An IPC plugin runs in its own process, so macOS normally treats its wx dialog
# as a separate application and pushes the PCB editor into the background.
#
# License: GPL-3.0-or-later

import platform
import sys
import requests
import subprocess
import time
from pathlib import Path


SYSTEM = "darwin"

def entrypoint(func):
    def wrapper(*args,**kwargs):
        if sys.platform == SYSTEM:
             return func(*args,**kwargs)
    return wrapper

@entrypoint
def prepare_app(*args):
    pass

@entrypoint
def attach_app(*args):
    pass

@entrypoint
def modal(*args):
    pass

@entrypoint
def save():
    pass

@entrypoint
def open(eeschema: bool = True, pcbnew: bool = True):
    pass
