import io
import os
import re
import requests

from bs4 import BeautifulSoup
from pypdf import PdfReader


WEBHOOK = os.environ["DISCORD_WEBHOOK"]

XTB_PDF_URL = "https://www.xtb.com/int/equity-table-current.pdf"

SOURCES = [
    {
        "name": "Premarket Gainers",
        "url": "https://stockanalysis.com/markets/premarket/gainers/",
        "type": "premarket"
    },
    {
        "name": "Premarket Losers",
        "url": "https://stockanalysis.com/markets/premarket/losers/",
        "type": "premarket"
    },
    {
        "name": "Most Active",
        "url": "https://stockanalysis.com/markets/active/",
        "type": "active"
    }
]

TOP_COUNT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131 Safari/537.36"
    )
}


def parse_number(value):
    if value is None:
        return 0

    text = (
        str(value)
        .replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
        .upper()
    )

    if not text or text in {"-", "N/A"}:
        return 0

    multiplier = 1

    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]

    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]

    elif text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]

    elif text.endswith("T"):
        multiplier = 1_000_000_000_000
        text = text[:-1]

    try:
        return float(text) * multiplier
    except ValueError:
        return 0


def format_money(value):
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"${value / 1_000:.1f}K"

    return f"${value:.0f}"


def format_volume(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value / 1_000:.1f}K"

    return f"{value:.0f}"


def load_xtb_symbols():
    print("Stahuji XTB Stock CFD seznam...")

    response = requests.get(
        XTB_PDF_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    reader = PdfReader(io.BytesIO(response.content))

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += "\n" + page_text

    symbols = set(
        re.findall(
            r"\b([A-Z0-9.-]+)\.US\b",
            text
        )
    )

    print(f"Nalezeno {len(symbols)} US CFD instrumentu na XTB.")

    if not symbols:
        raise Exception("Nepodarilo se nacist XTB CFD tickery.")

    return symbols


def load_stockanalysis(source):
    print(f"Stahuji: {source['name']}")

    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    table = soup.find("table")

    if not table:
        print(f"WARNING: Nenalezena tabulka: {source['name']}")
        return []

    rows = table.find_all("tr")[1:]

    results = []

    for row in rows:
        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        if source["type"] == "premarket":
            symbol = cols[1].get_text(strip=True).upper()
            company = cols[2].get_text(strip=True)
            change_text = cols[3].get_text(strip=True)
            price_text = cols[4].get_text(strip=True)
            volume_text = cols[5].get_text(strip=True)
            market_cap = cols[6].get_text(strip=True)

        else:
            symbol = cols[1].get_text(strip=True).upper()
            company = cols[2].get_text(strip=True)
            volume_text = cols[3].get_text(strip=True)
            price_text = cols[4].get_text(strip=True)
            change_text = cols[5].get_text(strip=True)
            market_cap = cols[6].get_text(strip=True)

        price = parse_number(price_text)
        volume = parse_number(volume_text)
        change = parse_number(change_text)

        if price <= 0:
            continue

        traded_value = price * volume

        results.append({
            "symbol": symbol,
            "company": company,
            "change": change,
            "change_text": change_text,
            "price": price,
            "volume": volume,
            "market_cap": market_cap,
            "traded_value": traded_value,
            "source": source["name"]
        })

    print(f"{source['name']}: {len(results)} zaznamu")

    return results


xtb_symbols = load_xtb_symbols()

all_stocks = {}

for source in SOURCES:
    stocks = load_stockanalysis(source)

    for stock in stocks:
        symbol = stock["symbol"]

        if symbol not in xtb_symbols:
            continue

        if symbol not in all_stocks:
            all_stocks[symbol] = stock
        else:
            existing = all_stocks[symbol]

            # Pokud stejný ticker najdeme vícekrát,
            # necháme variantu s vyšším traded value.
            if stock["traded_value"] > existing["traded_value"]:
                all_stocks[symbol] = stock


stocks = list(all_stocks.values())

print(f"Po XTB filtru: {len(stocks)} unikatnich tickeru")


def score(stock):
    """
    Jednoduché skóre:
    - pohyb ceny
    - traded value
    - volume
    """

    movement_score = min(abs(stock["change"]) * 3, 60)

    traded = stock["traded_value"]

    if traded >= 100_000_000:
        liquidity_score = 30
    elif traded >= 50_000_000:
        liquidity_score = 25
    elif traded >= 20_000_000:
        liquidity_score = 20
    elif traded >= 5_000_000:
        liquidity_score = 15
    elif traded >= 1_000_000:
        liquidity_score = 10
    else:
        liquidity_score = 3

    volume = stock["volume"]

    if volume >= 10_000_000:
        volume_score = 10
    elif volume >= 1_000_000:
        volume_score = 7
    elif volume >= 250_000:
        volume_score = 4
    else:
        volume_score = 1

    return round(
        movement_score +
        liquidity_score +
        volume_score
    )


for stock in stocks:
    stock["score"] = score(stock)


stocks.sort(
    key=lambda x: (
        x["score"],
        x["traded_value"]
    ),
    reverse=True
)

top = stocks[:TOP_COUNT]


if not top:
    message = (
        "⚠️ **XTB MARKET SCANNER**\n\n"
        "Nenalezeny zadne relevantni XTB CFD tickery."
    )

else:
    message = (
        "🚀 **TOP 10 XTB MARKET MOVERS**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, stock in enumerate(top, start=1):
        symbol = stock["symbol"]

        if stock["change"] > 0:
            movement = f"🟢 +{stock['change']:.2f}%"
        elif stock["change"] < 0:
            movement = f"🔴 {stock['change']:.2f}%"
        else:
            movement = "⚪ 0.00%"

        tradingview = (
            f"https://www.tradingview.com/chart/?symbol={symbol}"
        )

        message += (
            f"**{i}. {symbol}** — {movement}\n"
            f"💰 Cena: ${stock['price']:.2f}\n"
            f"📊 Volume: {format_volume(stock['volume'])}\n"
            f"💵 Traded: {format_money(stock['traded_value'])}\n"
            f"🏢 Market cap: {stock['market_cap']}\n"
            f"🔥 Score: **{stock['score']}/100**\n"
            f"📡 {stock['source']}\n"
            f"📈 [TradingView]({tradingview})\n\n"
        )

    message += (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏦 XTB Stock CFD only\n"
        "📊 StockAnalysis"
    )


# Discord má limit 2000 znaků.
# Když by zpráva byla moc dlouhá,
# rozdělíme ji na části.

MAX_LENGTH = 1900

parts = []

while len(message) > MAX_LENGTH:
    split_at = message.rfind("\n\n", 0, MAX_LENGTH)

    if split_at == -1:
        split_at = MAX_LENGTH

    parts.append(message[:split_at])
    message = message[split_at:].lstrip()

parts.append(message)


for part in parts:
    discord_response = requests.post(
        WEBHOOK,
        json={"content": part},
        timeout=15
    )

    discord_response.raise_for_status()


print("\n===== TOP STOCKS =====")

for stock in top:
    print(
        stock["symbol"],
        stock["change"],
        stock["volume"],
        stock["traded_value"],
        stock["score"],
        stock["source"]
    )
