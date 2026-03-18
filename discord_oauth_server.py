from flask import Flask, redirect, request, jsonify
import requests
import os

app = Flask(__name__)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")

user_data = {
    "Discord Username": "Not connected",
    "Discord Display Name": "Not connected",
    "Discord User ID": "Not connected",
    "Discord Email": "Not connected",
    "connected": False,
}


@app.route("/")
def home():
    return "OAuth server online", 200


@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        return "Missing Discord OAuth environment variables.", 500

    discord_url = (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=identify%20email"
        "&prompt=consent"
    )
    return redirect(discord_url)


@app.route("/callback")
def callback():
    global user_data

    code = request.args.get("code")
    if not code:
        return "Missing authorization code.", 400

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
            "https://discord.com/api/oauth2/token",
            data=token_payload,
            headers=token_headers,
            timeout=20
        )
        token_response.raise_for_status()
        token_json = token_response.json()
    except Exception as e:
        return f"Token exchange failed: {e}", 500

    access_token = token_json.get("access_token")
    if not access_token:
        return "No access token returned by Discord.", 500

    try:
        user_response = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20
        )
        user_response.raise_for_status()
        user_json = user_response.json()
    except Exception as e:
        return f"Failed to fetch Discord user data: {e}", 500

    username = user_json.get("username", "Unknown")
    discriminator = user_json.get("discriminator", "0")
    if discriminator and discriminator != "0":
        full_username = f"{username}#{discriminator}"
    else:
        full_username = username

    user_data = {
        "Discord Username": full_username,
        "Discord Display Name": user_json.get("global_name", "Unknown"),
        "Discord User ID": user_json.get("id", "Unknown"),
        "Discord Email": user_json.get("email", "Unknown"),
        "connected": True,
    }

    print("DISCORD DATA RECEIVED:", user_data)

    return """
    <html>
      <body style="background:#111;color:#fff;font-family:Arial;text-align:center;padding-top:60px;">
        <h2>Verification complete</h2>
        <p>You can close this window.</p>
      </body>
    </html>
    """


@app.route("/result")
def result():
    return jsonify(user_data)


@app.route("/reset")
def reset():
    global user_data
    user_data = {
        "Discord Username": "Not connected",
        "Discord Display Name": "Not connected",
        "Discord User ID": "Not connected",
        "Discord Email": "Not connected",
        "connected": False,
    }
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)