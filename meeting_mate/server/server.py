from flask import Flask, jsonify, session, redirect, request
import functools
import requests
from meeting_mate.mongo.mongo import INSTANCE as mongo
import os
from datetime import datetime
from meeting_mate.google.google_auth import build_google_auth_url, get_google_tokens, parse_jwt_token

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/api/login', methods=['GET'])
def login():
    # check if this is callback (has path/query parameters)
    if 'code' not in request.args:
        auth_url, state = build_google_auth_url()
        # for csrf protection
        session['state'] = state
        return redirect(auth_url)
    else:        
        # print("Callback", request.args)
        # check state
        if request.args.get('state') != session.get('state'):
            return jsonify({"error": "Invalid state"}), 400
        
        # get tokens
        code = request.args.get('code')
        tokens = get_google_tokens(code)

        #print("Tokens", tokens)

        user_info = parse_jwt_token(tokens["id_token"])
        #print("User info", user_info)

        user_record = {
            "sub": user_info["sub"],
            "name": user_info["name"],
            "picture": user_info["picture"],
            "given_name": user_info["given_name"],
            "email": user_info["email"],
            "tokens": {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "id_token": tokens["id_token"],
                "expires_at": datetime.fromtimestamp(user_info["exp"])
            }
        }

        mongo.store_user(user_record)
        session['user'] = user_record

        # Success! Redirect to home page
        return redirect("/")

@app.route("/", methods=['GET'])
def home():
    if 'user' in session:
        return f"Hello, {session['user']['name']}!"
    else:
        return "<a href='/api/login'>Login with Google</a>"

if __name__ == '__main__':
    app.run(debug=True, host='localhost')

