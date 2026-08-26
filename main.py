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

STOCKANALYSIS_URL = "https://stockanalysis.com/markets/premarket/gainers/"

# Aktualni oficialni XTB tabulka Stock CFD / ETF CFD
XTB_PDF_URL = "https://www.xtb.com/int/equity-table-current.pdf"

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
    """
    Prevede napriklad:
    23.5M -> 23 500 000
    850K  -> 850 000
    1.2B  -> 1 200 000 000
    """
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


# =========================
# 1. NACIST XTB CFD TICKERY
# =========================

print("Stahuji XTB Stock CFD seznam...")

xtb_response = requests.get(
    XTB_PDF_URL,
    headers=HEADERS,
    timeout=30
)

xtb_response.raise_for_status()

reader = PdfReader(io.BytesIO(xtb_response.content))

xtb_text = ""

for page in reader.pages:
    page_text = page.extract_text()

    if page_text:
        xtb_text += "\n" + page_text


# Hledame instrumenty typu:
# NVDA.US
# TSLA.US
# AAPL.US
#
# a nechame jen zakladni ticker:
# NVDA
# TSLA
# AAPL

xtb_symbols = set(
    re.findall(
        r"\b([A-Z0-9.-]+)\.US\b",
        xtb_text
    )
)

print(f"Nalezeno {len(xtb_symbols)} US CFD instrumentu na XTB.")


if not xtb_symbols:
    raise Exception(
        "Nepodarilo se nacist zadne XTB US CFD tickery."
    )


# =========================
# 2. PREMARKET GAINERS
# =========================

print("Stahuji StockAnalysis premarket gainery...")

response = requests.get(
    STOCKANALYSIS_URL,
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
        "Nenalezena tabulka s premarket gainery."
    )


rows = table.find_all("tr")[1:]

stocks = []


for row in rows:

    cols = row.find_all("td")

    if len(cols) < 7:
        continue

    symbol = cols[1].get_text(strip=True).upper()
    company = cols[2].get_text(strip=True)
    change = cols[3].get_text(strip=True)
    price_text = cols[4].get_text(strip=True)
    volume_text = cols[5].get_text(strip=True)
    market_cap = cols[6].get_text(strip=True)

    # =========================
    # XTB CFD FILTR
    # =========================

    if symbol not in xtb_symbols:
        print(f"SKIP {symbol} - neni XTB CFD")
        continue


    price = parse_number(price_text)
    volume = parse_number(volume_text)

    traded_value = price * volume


    stocks.append({
        "symbol": symbol,
        "company": company,
        "change": change,
        "price": price,
        "price_text": price_text,
        "volume": volume,
        "volume_text": volume_text,
        "market_cap": market_cap,
        "traded_value": traded_value,
    })


# StockAnalysis uz gainery radi podle %
top = stocks[:TOP_COUNT]


# =========================
# 3. DISCORD
# =========================

if not top:

    message = (
        "⚠️ **XTB PREMARKET SCANNER**\n\n"
        "Dnes nebyl mezi nactenymi premarket gainery "
        "nalezen zadny titul dostupny jako XTB Stock CFD."
    )

else:

    message = (
        "🚀 **TOP XTB PREMARKET GAINERS**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )


    for i, stock in enumerate(top, start=1):

        symbol = stock["symbol"]

        tradingview = (
            f"https://www.tradingview.com/chart/?symbol={symbol}"
        )

        message += (
            f"**{i}. {symbol} — {stock['change']}**\n"
            f"💰 Cena: ${stock['price']:.2f}\n"
            f"📊 Volume: {stock['volume_text']}\n"
            f"💵 Traded value: {format_money(stock['traded_value'])}\n"
            f"🏢 Market cap: {stock['market_cap']}\n"
            f"📈 [TradingView]({tradingview})\n\n"
        )


    message += (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏦 XTB Stock CFD only\n"
        "📡 Premarket: StockAnalysis"
    )


# Discord limit je 2000 znaku
message = message[:1950]


discord_response = requests.post(
    WEBHOOK,
    json={"content": message},
    timeout=15
)

discord_response.raise_for_status()


print("\n===== DISCORD MESSAGE =====")
print(message)
