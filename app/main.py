from fastapi import FastAPI, HTTPException, Header, Request, Response

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import jwt
import requests

import os
import time
from typing import Annotated

limiter = Limiter(key_func=get_remote_address,headers_enabled=True)
app = FastAPI()

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# This is an ultra-lightweight FastAPI app to serve Github IATs to authorised users in the Github Org.
# It can support 40 simultanious users 24/7 with a cost of <0.01USD a month

# Plugin users call the API to issue an IAT to them. 
# This takes place every ~1h during constant usage of the plugin, or whenever their token expires and a request needs to be sent by them.
# The server verifies they are apart of the org, then requests an IAT using a signed JWT

# You could in theory use a PAT instead, but good luck instructing a dozen freshers on how to do that!
# Accessing the Github API on behalf of an App with strict permissions is safer and we can track plugin usage among the team.


@app.get("/github/auth")
@limiter.limit("5/minute")
async def auth(request: Request, response: Response, Authorization: Annotated[str | None, Header()] = None):
    response = requests.get(
        f"https://api.github.com/user/memberships/orgs/{os.environ.get("ORG")}", 
        headers = {
            "Authorization": f"Bearer {Authorization}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    if response.status_code != 200:
        raise HTTPException(424, "Github User API is unavailable")
    in_org = response.json().get("state") == "active"
    if not in_org:
        raise HTTPException(401, "User not in organisation")
    jwt_payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,
        'iss': os.environ.get("CLIENT_ID")
    }
    signing_key = os.environ.get("APP_KEY_SECRET")
    encoded_jwt = jwt.encode(jwt_payload, signing_key, algorithm='RS256')
    response = requests.post(f"https://api.github.com/app/installations/{os.environ.get("INSTALLATION_ID")}/access_tokens",
        headers = {
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if response.status_code != 201:
        raise HTTPException(424, "Github App API is unavailable")
    data = response.json()
    return {
        "access_token": data["token"],
        "expires": data["expires_at"]
    }