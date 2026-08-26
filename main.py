import os
import requests

API_KEY = os.environ["FINNHUB_API_KEY"]
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

symbol = "NVDA"

url = "https://finnhub.io/api/v1/quote"

response = requests.get(
    url,
    params={
        "symbol": symbol,
        "token": API_KEY
    },
    timeout=15
)

data = response.json()

message = (
    f"📊 TEST DATA — {symbol}\n\n"
    f"💰 Cena: ${data.get('c')}\n"
    f"📈 Změna: {data.get('dp')} %\n"
    f"⬆️ High: ${data.get('h')}\n"
    f"⬇️ Low: ${data.get('l')}\n"
)

requests.post(
    WEBHOOK,
    json={"content": message},
    timeout=15
)

print(data)
