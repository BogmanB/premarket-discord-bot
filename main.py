import io
import os
import re
import requests

from bs4 import BeautifulSoup
from pypdf import PdfReader


# =========================
# NASTAVENI
# =========================

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

XTB_PDF_URL = "https://www.xtb.com/int/equity-table-current.pdf"

GAINERS_URL = "https://stockanalysis.com/markets/premarket/gainers/"
LOSERS_URL = "https://stockanalysis.com/markets/premarket/losers/"

TOP_COUNT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131 Safari/537.36"
    )
}


# =========================
# POMOCNE FUNKCE
# =========================

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
        return f"${value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"${value / 1_000:.1f}K"

    return f"${value:.0f}"


def format_volume(value):
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"{value / 1_000:.0f}K"

    return f"{value:.0f}"


# =========================
# TRADE SCORE
# =========================

def calculate_score(stock):
    """
    Score 0-100.

    Hodnotime:
    45 bodu = velikost pohybu
    35 bodu = traded value / likvidita
    20 bodu = volume

    Neni to doporuceni BUY/SELL.
    Je to priorita, na co se podivat.
    """

    movement = abs(stock["change"])
    traded = stock["traded_value"]
    volume = stock["volume"]

    # 0-45 bodu za pohyb
    if movement >= 20:
        movement_score = 45
    elif movement >= 15:
        movement_score = 40
    elif movement >= 10:
        movement_score = 35
    elif movement >= 7:
        movement_score = 28
    elif movement >= 5:
        movement_score = 22
    elif movement >= 3:
        movement_score = 15
    else:
        movement_score = 7

    # 0-35 bodu za zobchodovanou hodnotu
    if traded >= 500_000_000:
        traded_score = 35
    elif traded >= 200_000_000:
        traded_score = 32
    elif traded >= 100_000_000:
        traded_score = 29
    elif traded >= 50_000_000:
        traded_score = 25
    elif traded >= 20_000_000:
        traded_score = 20
    elif traded >= 5_000_000:
        traded_score = 14
    elif traded >= 1_000_000:
        traded_score = 8
    else:
        traded_score = 3

    # 0-20 bodu za volume
    if volume >= 20_000_000:
        volume_score = 20
    elif volume >= 10_000_000:
        volume_score = 18
    elif volume >= 5_000_000:
        volume_score = 16
    elif volume >= 1_000_000:
        volume_score = 13
    elif volume >= 500_000:
        volume_score = 10
    elif volume >= 100_000:
        volume_score = 6
    else:
        volume_score = 2

    return min(
        movement_score + traded_score + volume_score,
        100
    )


# =========================
# XTB CFD SEZNAM
# =========================

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

    print(
        f"Nalezeno {len(symbols)} US CFD instrumentu na XTB."
    )

    if not symbols:
        raise Exception(
            "Nepodarilo se nacist XTB US CFD tickery."
        )

    return symbols


# =========================
# STOCKANALYSIS
# =========================

def load_movers(url, direction, xtb_symbols):

    print(f"Stahuji {direction}...")

    response = requests.get(
        url,
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
        raise Exception(
            f"Nenalezena tabulka pro {direction}."
        )

    rows = table.find_all("tr")[1:]

    stocks = []

    for row in rows:

        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        symbol = cols[1].get_text(strip=True).upper()
        company = cols[2].get_text(strip=True)
        change_text = cols[3].get_text(strip=True)
        price_text = cols[4].get_text(strip=True)
        volume_text = cols[5].get_text(strip=True)
        market_cap = cols[6].get_text(strip=True)

        if symbol not in xtb_symbols:
            print(
                f"SKIP {symbol} - neni XTB CFD"
            )
            continue

        change = parse_number(change_text)

        # U loseru muze parser vratit kladne cislo,
        # proto smer pojistime.
        if direction == "losers":
            change = -abs(change)
        else:
            change = abs(change)

        price = parse_number(price_text)
        volume = parse_number(volume_text)

        if price <= 0:
            continue

        traded_value = price * volume

        stock = {
            "symbol": symbol,
            "company": company,
            "change": change,
            "price": price,
            "volume": volume,
            "market_cap": market_cap,
            "traded_value": traded_value
        }

        stock["score"] = calculate_score(stock)

        stocks.append(stock)

    print(
        f"{direction}: {len(stocks)} XTB tickeru"
    )

    return stocks


# =========================
# NACIST DATA
# =========================

xtb_symbols = load_xtb_symbols()

gainers = load_movers(
    GAINERS_URL,
    "gainers",
    xtb_symbols
)

losers = load_movers(
    LOSERS_URL,
    "losers",
    xtb_symbols
)


# StockAnalysis je uz serazeny podle pohybu.
# Nechame TOP 10 XTB z kazde strany.

top_gainers = gainers[:TOP_COUNT]
top_losers = losers[:TOP_COUNT]


# =========================
# DISCORD SLOUPCE
# =========================

def build_column(stocks, emoji):

    if not stocks:
        return "Dnes nic."

    lines = []

    for i, stock in enumerate(stocks, start=1):

        symbol = stock["symbol"]

        tradingview = (
            f"https://www.tradingview.com/chart/"
            f"?symbol={symbol}"
        )

        sign = "+" if stock["change"] > 0 else ""

        line = (
            f"**{i}. [{symbol}]({tradingview})** "
            f"`{sign}{stock['change']:.2f}%`\n"
            f"{emoji} ${stock['price']:.2f} | "
            f"Vol {format_volume(stock['volume'])}\n"
            f"💵 {format_money(stock['traded_value'])} | "
            f"🔥 {stock['score']}/100"
        )

        lines.append(line)

    text = "\n\n".join(lines)

    # Discord field ma limit 1024 znaku.
    return text[:1020]


gainers_text = build_column(
    top_gainers,
    "🟢"
)

losers_text = build_column(
    top_losers,
    "🔴"
)


embed = {
    "title": "📊 XTB PREMARKET SCANNER",
    "description": (
        "Premarket movers dostupne jako **XTB Stock CFD**.\n"
        "Kliknutim na ticker otevres TradingView."
    ),
    "fields": [
        {
            "name": "🟢 TOP GAINERS",
            "value": gainers_text,
            "inline": True
        },
        {
            "name": "🔴 TOP LOSERS",
            "value": losers_text,
            "inline": True
        }
    ],
    "footer": {
        "text": (
            "StockAnalysis • XTB CFD filter • "
            "Trade Score = movement + liquidity + volume"
        )
    }
}


payload = {
    "embeds": [embed]
}


discord_response = requests.post(
    WEBHOOK,
    json=payload,
    timeout=15
)

discord_response.raise_for_status()


# =========================
# LOG
# =========================

print("\n===== GAINERS =====")

for stock in top_gainers:
    print(
        stock["symbol"],
        stock["change"],
        stock["volume"],
        stock["traded_value"],
        stock["score"]
    )


print("\n===== LOSERS =====")

for stock in top_losers:
    print(
        stock["symbol"],
        stock["change"],
        stock["volume"],
        stock["traded_value"],
        stock["score"]
    )
