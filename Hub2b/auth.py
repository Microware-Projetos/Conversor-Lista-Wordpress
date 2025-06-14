import requests
import json
import os
from datetime import datetime, timedelta

TOKEN_FILE = "token.json"

CLIENT_ID = "iPFSv5W9KAqCsVcBC14z95u4B8ezzTz3"
CLIENT_SECRET = "WgibMLsaceE04lLMoM38ViJDY4O03try"
USERNAME = "2792microware@microware"
PASSWORD = "84c7dutc6fm35us45zvt"

LOGIN_URL = "https://rest.hub2b.com.br/oauth2/login"
REFRESH_URL = "https://rest.hub2b.com.br/oauth2/token"


def save_token(data):
    data["created_at"] = datetime.utcnow().isoformat()
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def is_token_expired(token_data):
    created = datetime.fromisoformat(token_data["created_at"])
    expires_in = token_data["expires_in"]
    return datetime.utcnow() > created + timedelta(seconds=expires_in - 60)


def login():
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "password",
        "scope": "catalog",
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(LOGIN_URL, json=payload)
    response.raise_for_status()
    token_data = response.json()
    save_token(token_data)
    return token_data


def refresh(token_data):
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"]
    }
    response = requests.post(REFRESH_URL, json=payload)
    response.raise_for_status()
    new_token_data = response.json()
    save_token(new_token_data)
    return new_token_data


def get_token():
    token_data = load_token()

    if not token_data:
        return login()

    if is_token_expired(token_data):
        try:
            return refresh(token_data)
        except Exception:
            return login()

    return token_data