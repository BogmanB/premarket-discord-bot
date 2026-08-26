import os
import requests

webhook_url = os.environ.get("DISCORD_WEBHOOK")

if not webhook_url:
    print("DISCORD_WEBHOOK není nastaven.")
else:
    response = requests.post(
        webhook_url,
        json={"content": "🚀 Premarket bot funguje!"},
        timeout=15
    )

    print(response.status_code)
