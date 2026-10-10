import requests
from utils import build, settings


def log(*message):
    response = requests.post(
        url=settings.get("debug/remote_url/Info"),
        params={
            "data": " ".join(map(str, message))
        }
    )