import requests
from bs4 import BeautifulSoup
import os

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

URL = "https://stockanalysis.com/markets/premarket/gainers/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(
    URL,
    headers=headers,
    timeout=20
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

table = soup.find("table")

if not table:
    raise Exception("Nenašel jsem tabulku s premarket gainery.")

rows = table.find_all("tr")[1:]

stocks = []

for row in rows:
    cols = row.find_all("td")

    if len(cols) < 7:
        continue

    symbol = cols[1].get_text(strip=True)
    company = cols[2].get_text(strip=True)
    change = cols[3].get_text(strip=True)
    price = cols[4].get_text(strip=True)
    volume = cols[5].get_text(strip=True)
    market_cap = cols[6].get_text(strip=True)

    stocks.append({
        "symbol": symbol,
        "company": company,
        "change": change,
        "price": price,
        "volume": volume,
        "market_cap": market_cap
    })

top = stocks[:10]

message = "🚀 **TOP PREMARKET GAINERS**\n\n"

for i, stock in enumerate(top, start=1):

    message += (
        f"**{i}. {stock['symbol']}** — {stock['change']}\n"
        f"💰 ${stock['price']} | "
        f"📊 Vol: {stock['volume']} | "
        f"🏢 MC: {stock['market_cap']}\n\n"
    )

message += "📡 Source: StockAnalysis"

requests.post(
    WEBHOOK,
    json={"content": message[:1900]},
    timeout=15
)

print(message)
