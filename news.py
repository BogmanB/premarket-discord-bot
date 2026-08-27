import os
import requests
from datetime import datetime, timedelta, timezone


FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131 Safari/537.36"
    )
}


def _format_news_time(timestamp):
    """
    Prevede Finnhub unix timestamp na citelny cas v UTC.
    """
    if not timestamp:
        return ""

    try:
        dt = datetime.fromtimestamp(
            int(timestamp),
            tz=timezone.utc
        )

        return dt.strftime("%d.%m. %H:%M UTC")

    except Exception:
        return ""


def _clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def get_latest_news(symbol, days_back=3, limit=5):
    """
    Vrati seznam nejnovejsich zprav pro ticker.

    Priklad vystupu:

    [
        {
            "headline": "...",
            "summary": "...",
            "source": "Reuters",
            "url": "https://...",
            "datetime": 123456789,
            "time_text": "27.08. 08:15 UTC"
        }
    ]

    Pokud Finnhub nic nenajde nebo nastane chyba,
    vrati prazdny seznam.
    """

    symbol = symbol.upper().strip()

    today = datetime.now(timezone.utc).date()

    date_from = today - timedelta(days=days_back)

    params = {
        "symbol": symbol,
        "from": date_from.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY
    }

    try:
        response = requests.get(
            FINNHUB_NEWS_URL,
            params=params,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            print(
                f"NEWS {symbol}: Finnhub nevratil seznam."
            )
            return []

        cleaned = []

        for item in data:

            headline = _clean_text(
                item.get("headline")
            )

            if not headline:
                continue

            timestamp = item.get("datetime", 0)

            cleaned.append({
                "headline": headline,
                "summary": _clean_text(
                    item.get("summary")
                ),
                "source": _clean_text(
                    item.get("source")
                ),
                "url": _clean_text(
                    item.get("url")
                ),
                "datetime": timestamp,
                "time_text": _format_news_time(
                    timestamp
                )
            })

        cleaned.sort(
            key=lambda x: x["datetime"],
            reverse=True
        )

        result = cleaned[:limit]

        print(
            f"NEWS {symbol}: nalezeno {len(result)} zprav."
        )

        return result

    except Exception as e:
        print(
            f"NEWS ERROR {symbol}: {e}"
        )

        return []


def get_best_news(symbol):
    """
    Vrati jednu nejcerstvejsi relevantni zpravu.

    Kdyz nic neni:
    None
    """

    news = get_latest_news(
        symbol=symbol,
        days_back=3,
        limit=5
    )

    if not news:
        return None

    return news[0]


def get_news_display(symbol):
    """
    Jednoduchy helper pro Discord.

    Vrati slovnik:
    {
        "headline": "...",
        "source": "...",
        "url": "...",
        "time": "..."
    }

    nebo None.
    """

    item = get_best_news(symbol)

    if not item:
        return None

    return {
        "headline": item["headline"],
        "source": item["source"],
        "url": item["url"],
        "time": item["time_text"],
        "summary": item["summary"]
    }
