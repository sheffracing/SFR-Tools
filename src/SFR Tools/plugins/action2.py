import requests

requests.get(url="http://127.0.0.1:7084/")

requests.post(url="http://127.0.0.1:7084/data?data=hello")

requests.post(
    url="http://127.0.0.1:7084/data",
    params={
        "data": "hello"
    }
)