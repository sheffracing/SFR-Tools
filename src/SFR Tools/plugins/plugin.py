import requests
import json
import sys
import subprocess
import time

from kipy import KiCad
from kipy.errors import ConnectionError, FutureVersionError, ApiError
import kipy.proto.common.types as ProtoType
from kipy.proto.common.commands import editor_commands_pb2, project_commands_pb2
import kipy.common_types as Type

from google.protobuf.empty_pb2 import Empty
from utils.log import log
from utils import settings, build
from pathlib import Path

import utils.platform.darwin as darwin
import utils.platform.win32 as win

import time
import re

class Plugin(KiCad):
    def __init__(self, socket_path = None, client_name = None, kicad_token = None, timeout_ms = 2000):
        super().__init__(socket_path, client_name, kicad_token, timeout_ms)
        self.version = self.get_version()
        self.api_compatible = self.check_version()
        if not self.api_compatible:
            raise FutureVersionError("Python package is not built for this version of the Kicad IPC API")
        try:
            self.ping()
        except:
            ApiError("Cannot Communicate with the Kicad instance")
        self.board = self.get_board()
        #self.schematic = self.get_schematic()
        self.project = self.get_project(self.board.document)
        self.binary = self.get_kicad_binary_path("kicad")
        self.branch_name = f"{settings.get('info/car')}-{Path(self.project.path).name}-{settings.get('github/login')}".lower()
        self.settings_path = self.get_plugin_settings_path(build.get("identifier"))
    def isConnected(self) -> bool:
        try:
            self.ping()
            return True
        except:
            return False
    def GetDir(self):
        return self.project.path
    
    def Save(self):
        self.board.save()
        #self.schematic.save()
        darwin.save()
        win.save()

    def __launchMac(self, path: str = None):
        if sys.platform != "darwin":
            return
        payload = ["open", "-a", "KiCad"]
        if path:
            payload.append(path)

        process = subprocess.run(
            payload,
            capture_output=True,
            text=True
        )

    def __quitMac(self, force: bool = False):
        if sys.platform != "darwin":
            return
        if force:
            pid = str(darwin.get_pid("KiCad"))
            subprocess.run(["kill", "-9", pid])
        else:
            subprocess.run(["osascript","-e",'tell application "KiCad" to quit'])

    def __launchWin(self, path: str = None):
        if sys.platform != "win32":
            return
        payload = [self.binary]
        if path:
            payload.append(path)
        subprocess.Popen(payload)

    def __quitWin(self, force: bool = False):
        if sys.platform != "win32":
            return
        if force:
            subprocess.run(
                ["taskkill", "/F", "/IM", executable],
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                ["taskkill", "/IM", self.binary],
                capture_output=True,
                text=True,
            )
    def quit(self, force: bool = False):
        self.__quitMac(force)
        self.__quitWin(force)
        time.sleep(0.1)
    def open(self, path: Path = None, eeschema: bool = False, pcbnew: bool = False):
        self.__launchMac(str(path) if path else None)
        self.__launchWin(str(path) if path else None)
        time.sleep(0.5)
        darwin.open(eeschema, pcbnew)
        win.open(eeschema, pcbnew)
    def is_file_symbol(path: Path) -> tuple[bool, str]:
        if not path or path.suffix != ".kicad_sym":
            return False, "File is nil or has incorrect suffix"
        if re.match("\\(kicad_symbol_lib[\s\S]*\\(symbol[\s\S]*\\)$"):
            return True, None
        else:
            return False, "File is malformed or does not contain a symbol"
    def merge_sym():
        pass