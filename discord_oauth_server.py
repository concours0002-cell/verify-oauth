import time
import webbrowser
import requests

BASE_URL = "https://verify-oauth.onrender.com"

LOGIN_URL = f"{BASE_URL}/login"
RESULT_URL = f"{BASE_URL}/result"


def get_discord_identity(timeout_seconds=180):
    # Vérifie d'abord si une auth existe déjà
    try:
        existing = requests.get(RESULT_URL, timeout=5)
        if existing.status_code == 200:
            data = existing.json()
            if data.get("connected") is True:
                return {
                    "Discord Username": data.get("Discord Username", "Unknown"),
                    "Discord Display Name": data.get("Discord Display Name", "Unknown"),
                    "Discord User ID": data.get("Discord User ID", "Unknown"),
                    "Discord Email": data.get("Discord Email", "Unknown"),
                    "Discord In Server": "Yes" if data.get("in_server") else "No",
                }
    except Exception:
        pass

    # Lance OAuth UNE SEULE FOIS
    webbrowser.open(LOGIN_URL)

    start = time.time()

    while time.time() - start < timeout_seconds:
        try:
            resp = requests.get(RESULT_URL, timeout=5)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("connected") is True:
                    return {
                        "Discord Username": data.get("Discord Username", "Unknown"),
                        "Discord Display Name": data.get("Discord Display Name", "Unknown"),
                        "Discord User ID": data.get("Discord User ID", "Unknown"),
                        "Discord Email": data.get("Discord Email", "Unknown"),
                        "Discord In Server": "Yes" if data.get("in_server") else "No",
                    }

            elif resp.status_code == 429:
                time.sleep(8)

        except Exception:
            pass

        time.sleep(3)

    return {
        "Discord Username": "Not connected",
        "Discord Display Name": "Not connected",
        "Discord User ID": "Not connected",
        "Discord Email": "Not connected",
        "Discord In Server": "No",
    }