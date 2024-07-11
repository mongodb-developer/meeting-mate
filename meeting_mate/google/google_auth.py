
import base64
from datetime import datetime
import json
import random
import string
from dotenv import dotenv_values
import requests
from meeting_mate.mongo.mongo import INSTANCE as mongo
from google.oauth2.credentials import Credentials


env_values = dotenv_values()

google_config = {
    "client_id": env_values.get("google_client_id"),
    "client_secret": env_values.get("google_client_secret"),
    "redirect_uri": "http://localhost:5000/api/login",
    "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/v2/auth",
    "scopes" : ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/userinfo.profile", "email"]
}

def build_google_auth_url():
    base = google_config["auth_uri"]
    base+= "?client_id=" + google_config["client_id"]
    base+= "&redirect_uri=" + google_config["redirect_uri"]
    base+= "&response_type=code"
    base+= "&access_type=offline"
    base+= "&prompt=consent select_account"    
    base+= "&scope=" + " ".join(google_config["scopes"])

    # generate short random string for state
    state = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    base+= "&state=" + state

    return base, state

# call the https://oauth2.googleapis.com/token API to fetch tokens
def get_google_tokens(code):
    # prepare the request
    data = {
        "code": code,
        "client_id": google_config["client_id"],
        "client_secret": google_config["client_secret"],
        "redirect_uri": google_config["redirect_uri"],
        "grant_type": "authorization_code",
        "scope": " ".join(google_config["scopes"])
    }
    
    # make the request
    response = requests.post("https://oauth2.googleapis.com/token", data=data)
    if response.status_code != 200:
        raise requests.HTTPError(response.text)

    return response.json()

# call https://oauth2.googleapis.com/token to refresh token
def refresh_tokens(token):
    data = {
        "client_id": env_values.get("google_client_id"),
        "client_secret": env_values.get("google_client_secret"),
        "redirect_uri": "http://localhost:5000/api/login",
        "scope": " ".join(google_config["scopes"]),
        "refresh_token": token,
        "grant_type": "refresh_token"
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=data)
    return response.json()

def parse_jwt_token(token):
    parts = token.split('.')
    return json.loads(base64.b64decode(parts[1] + '===').decode('utf-8'))


def update_access_tokens(refresh_token):
    tokens = refresh_tokens(refresh_token)
    user_info = parse_jwt_token(tokens["id_token"])
    
    user_record = {
        "sub": user_info["sub"],                
        "tokens": {
            "access_token": tokens["access_token"],
            "refresh_token": refresh_token,
            "id_token": tokens["id_token"],
            "expires_at": datetime.fromtimestamp(user_info["exp"])
        }
    }
    if "name" in user_info:
        user_record["name"] = user_info["name"]
    if "picture" in user_info:
        user_record["picture"] = user_info["picture"]
    if "given_name" in user_info:
        user_record["given_name"] = user_info["given_name"]

    mongo.store_user(user_record)
    return user_record

def getUserCredentials(user_id):
    user = mongo.db.users.find_one({"sub": user_id})

    expires_at = user.get("tokens").get("expires_at")
    if expires_at < datetime.now():
        print("Access token expired, attempting to refresh...")
        # refresh token
        refresh_token = user.get("tokens").get("refresh_token")
        user = update_access_tokens(refresh_token)

    access_token = user.get("tokens").get("access_token")
    credentials = Credentials(token=access_token)
    return credentials