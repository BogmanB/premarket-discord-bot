import os
import requests
import time
from datetime import datetime

API_KEY = os.environ["FINNHUB_API_KEY"]
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

# Akcie, které zatím budeme sledovat
SYMBOLS = [
    "NVDA",
    "AMD",
    "TSLA",
    "AAPL",
    "AMZN",
    "META",
    "MSFT",
    "GOOGL",
    "PLTR",
    "SMCI",
    "COIN",
    "MSTR",
    "AVGO",
    "ARM",
    "INTC",
]

results = []

for symbol in SYMBOLS:
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={
                "symbol": symbol,
                "token": API_KEY
            },
            timeout=15
        )

        data = response.json()

        price = data.get("c")
        change = data.get("dp")

        if price is not None and change is not None:
            results.append({
                "symbol": symbol,
                "price": price,
                "change": change
            })

        # Ať zbytečně nebombardujeme API
        time.sleep(1)

    except Exception as e:
        print(f"Chyba u {symbol}: {e}")

# Největší růst nahoru
results.sort(
    key=lambda x: x["change"],
    reverse=True
)

top = results[:10]

date = datetime.now().strftime("%d.%m.%Y")

message = f"🚀 **PREMARKET WATCHLIST — {date}**\n\n"

for i, stock in enumerate(top, start=1):

    emoji = "🟢" if stock["change"] >= 0 else "🔴"

    message += (
        f"**{i}. {stock['symbol']}** "
        f"{emoji} {stock['change']:+.2f}% "
        f"— ${stock['price']:.2f}\n"
    )

message += "\n📊 Data: Finnhub"

requests.post(
    WEBHOOK,
    json={"content": message},
    timeout=15
)

print(message)
