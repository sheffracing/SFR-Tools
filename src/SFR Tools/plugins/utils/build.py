import json
from pathlib import Path

path = Path(__file__).parents[1] / "data" / f"{Path(__file__).name.removesuffix(Path(__file__).suffix)}.json"

def get(address: str):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    value = data
    for key in address.split("/"):
        value = value[key]

    return value


def set(address: str, value):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    keys = address.split("/")
    target = data

    for key in keys[:-1]:
        target = target[key]

    target[keys[-1]] = value

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

