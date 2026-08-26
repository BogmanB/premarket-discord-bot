import os
import requests

TWELVE_KEY = os.environ["TWELVE_DATA_API_KEY"]
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

url = "https://api.twelvedata.com/market_movers/stocks"

response = requests.get(
    url,
    params={
        "apikey": TWELVE_KEY,
        "country": "United States"
    },
    timeout=20
)

data = response.json()

print(data)

message = "📡 Twelve Data test\n\n"

if isinstance(data, dict):
    for key in data.keys():
        message += f"• {key}\n"

requests.post(
    WEBHOOK,
    json={"content": message[:1900]},
    timeout=15
)
