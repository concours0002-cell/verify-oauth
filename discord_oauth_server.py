from flask import Flask, redirect, request, jsonify, session
import requests
import os
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change-me-now")

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api"


def empty_result():
    return {
        "Discord Username": "Not connected",
        "Discord Display Name": "Not connected",
        "Discord User ID": "Not connected",
        "Discord Email": "Not connected",
        "connected": False,
        "in_server": False,
    }


@app.route("/")
def home():
    return "OAuth server online", 200


@app.route("/reset")
def reset():
    session.pop("oauth_state", None)
    session.pop("discord_result", None)
    return jsonify({"ok": True})


@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        return "Missing Discord OAuth environment variables.", 500

    existing = session.get("discord_result")
    if existing and existing.get("connected") is True:
        return redirect("/result")

    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state

    auth_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=identify%20email%20guilds"
        f"&state={state}"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return "Missing authorization code.", 400

    expected_state = session.get("oauth_state")
    if not expected_state or not state or state != expected_state:
        return "Invalid OAuth state. Close this tab and restart from /login.", 400

    token_payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    token_headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        token_response = requests.post(
            DISCORD_TOKEN_URL,
            data=token_payload,
            headers=token_headers,
            timeout=20
        )

        if token_response.status_code == 429:
            return "Too many requests. Wait 30 seconds and try again.", 429

        token_response.raise_for_status()
        token_json = token_response.json()
    except Exception as e:
        return f"Token exchange failed: {e}", 500

    access_token = token_json.get("access_token")
    if not access_token:
        return "No access token returned by Discord.", 500

    api_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        me_response = requests.get(
            f"{DISCORD_API_URL}/users/@me",
            headers=api_headers,
            timeout=20
        )

        if me_response.status_code == 429:
            return "Too many requests while fetching user info. Wait 30 seconds and try again.", 429

        me_response.raise_for_status()
        me_json = me_response.json()
    except Exception as e:
        return f"Failed to fetch Discord user data: {e}", 500

    in_server = False

    if GUILD_ID:
        try:
            guilds_response = requests.get(
                f"{DISCORD_API_URL}/users/@me/guilds",
                headers=api_headers,
                timeout=20
            )

            if guilds_response.status_code == 429:
                return "Too many requests while checking server membership. Wait 30 seconds and try again.", 429

            guilds_response.raise_for_status()
            guilds = guilds_response.json()
            in_server = any(str(g.get("id")) == str(GUILD_ID) for g in guilds)
        except Exception as e:
            return f"Failed to fetch guild list: {e}", 500
    else:
        in_server = True

    username = me_json.get("username", "Unknown")
    discriminator = me_json.get("discriminator", "0")
    full_username = f"{username}#{discriminator}" if discriminator and discriminator != "0" else username

    result = {
        "Discord Username": full_username,
        "Discord Display Name": me_json.get("global_name", "Unknown"),
        "Discord User ID": me_json.get("id", "Unknown"),
        "Discord Email": me_json.get("email", "Unknown"),
        "connected": True,
        "in_server": in_server,
    }

    session["discord_result"] = result
    session.pop("oauth_state", None)

    print("DISCORD DATA RECEIVED:", result)

    return redirect("/result")


@app.route("/result")
def result():
    return jsonify(session.get("discord_result", empty_result()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)
