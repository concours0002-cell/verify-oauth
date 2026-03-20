from flask import Flask, redirect, request, jsonify
import requests
import os
import secrets
import time

app = Flask(__name__)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_BASE = os.environ.get("DISCORD_REDIRECT_BASE", "https://verify-oauth-production.up.railway.app")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api"

# stockage simple en mémoire par session
oauth_sessions = {}


def empty_result():
    return {
        "Discord Username": "Not connected",
        "Discord Display Name": "Not connected",
        "Discord User ID": "Not connected",
        "Discord Email": "Not connected",
        "connected": False,
        "in_server": False,
        "status": "pending",
    }


def cleanup_sessions(max_age_seconds=900):
    now = time.time()
    expired = []
    for sid, item in oauth_sessions.items():
        if now - item.get("created_at", now) > max_age_seconds:
            expired.append(sid)
    for sid in expired:
        oauth_sessions.pop(sid, None)


@app.route("/")
def home():
    return "OAuth server online", 200


@app.route("/start")
def start():
    cleanup_sessions()

    session_id = secrets.token_urlsafe(24)
    state = secrets.token_urlsafe(24)

    oauth_sessions[session_id] = {
        "created_at": time.time(),
        "state": state,
        "result": empty_result(),
    }

    return jsonify({
        "session_id": session_id,
        "login_url": f"{REDIRECT_BASE}/login?session_id={session_id}"
    })


@app.route("/login")
def login():
    cleanup_sessions()

    session_id = request.args.get("session_id", "")
    if not session_id or session_id not in oauth_sessions:
        return "Invalid session.", 400

    state = oauth_sessions[session_id]["state"]
    redirect_uri = f"{REDIRECT_BASE}/callback"

    auth_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=identify%20email%20guilds"
        f"&state={state}:{session_id}"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    cleanup_sessions()

    code = request.args.get("code")
    combined_state = request.args.get("state", "")

    if not code:
        return "Missing authorization code.", 400

    if ":" not in combined_state:
        return "Invalid state.", 400

    state, session_id = combined_state.split(":", 1)

    if session_id not in oauth_sessions:
        return "Session expired or invalid.", 400

    saved_state = oauth_sessions[session_id]["state"]
    if state != saved_state:
        return "Invalid OAuth state.", 400

    redirect_uri = f"{REDIRECT_BASE}/callback"

    try:
        token_response = requests.post(
            DISCORD_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=20,
        )

        token_response.raise_for_status()
        token_json = token_response.json()
        access_token = token_json.get("access_token")

        if not access_token:
            raise RuntimeError("No access token")

        headers = {"Authorization": f"Bearer {access_token}"}

        me_response = requests.get(
            f"{DISCORD_API_URL}/users/@me",
            headers=headers,
            timeout=20,
        )
        me_response.raise_for_status()
        me_json = me_response.json()

        in_server = False
        if GUILD_ID:
            guilds_response = requests.get(
                f"{DISCORD_API_URL}/users/@me/guilds",
                headers=headers,
                timeout=20,
            )
            guilds_response.raise_for_status()
            guilds = guilds_response.json()
            in_server = any(str(g.get("id")) == str(GUILD_ID) for g in guilds)
        else:
            in_server = True

        username = me_json.get("username", "Unknown")
        discriminator = me_json.get("discriminator", "0")
        full_username = f"{username}#{discriminator}" if discriminator and discriminator != "0" else username

        oauth_sessions[session_id]["result"] = {
            "Discord Username": full_username,
            "Discord Display Name": me_json.get("global_name", "Unknown"),
            "Discord User ID": me_json.get("id", "Unknown"),
            "Discord Email": me_json.get("email", "Unknown"),
            "connected": True,
            "in_server": in_server,
            "status": "done",
        }

        return """
        <html>
        <body style="background:#111;color:#fff;font-family:Arial;text-align:center;padding-top:60px;">
            <h2>Discord connected</h2>
            <p>You can close this window and return to the application.</p>
        </body>
        </html>
        """

    except Exception as e:
        oauth_sessions[session_id]["result"] = {
            "Discord Username": "Not connected",
            "Discord Display Name": "Not connected",
            "Discord User ID": "Not connected",
            "Discord Email": "Not connected",
            "connected": False,
            "in_server": False,
            "status": f"error: {str(e)}",
        }
        return f"OAuth failed: {e}", 500


@app.route("/result/<session_id>")
def result(session_id):
    cleanup_sessions()

    if session_id not in oauth_sessions:
        return jsonify({
            "connected": False,
            "in_server": False,
            "status": "invalid_session"
        }), 404

    return jsonify(oauth_sessions[session_id]["result"])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)
