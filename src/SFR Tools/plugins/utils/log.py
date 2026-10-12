import requests
from requests.exceptions import ConnectionError
import traceback
import pickle
import base64
from datetime import datetime
from pathlib import Path
import hashlib
import json
from utils import build, settings

log_path: Path = Path(__file__).parents[1] / "data" / settings.get("debug/log_file")

def silence(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            pass
    return wrapper
@silence
def __local(*message):
    with log_path.open("a", encoding="utf-8") as f:
        data = pickle.dumps(obj = message)
        f.write(f'[{settings.get("github/login")}][{build.get("version")}][{datetime.now().isoformat()}] | {base64.b64encode(data).decode("ascii")}\n')

@silence
def __remote(*message):
    data = pickle.dumps(obj = message)
    body = {
        "user": settings.get("github/login"),
        "version": build.get("version"),
        "dt": datetime.now().isoformat(),
        "message": base64.b64encode(data).decode("ascii")
    }
    sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
    try:
        response = requests.post(
            url = settings.get("debug"),
            headers={
                "sha_256": sha
            },
            json = body
        )
        if response.status_code != 200:
            __local(f"Connection refused (HTTP {response.status_code}), {response.text}")
    except ConnectionError:
        __local(f"ConnectionError when sending remote logging details to: {settings.get('debug/remote_url/Info')}")
    except:
        __local(traceback.format_exc())

@silence
def log(*message):
    if settings.get("debug/remote_logging") == True:
        __remote(*message)
    if settings.get("debug/local_logging") == True:
        __local(*message)
