"""Register the configured Telegram bot with the deployed HTTPS backend."""

import argparse
from urllib.parse import urlsplit

import requests

from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS URL ending in /api/v1/telegram/webhook")
    url = parser.parse_args().url
    destination = urlsplit(url)
    if (
        destination.scheme != "https"
        or not destination.hostname
        or destination.username
        or destination.query
        or destination.fragment
        or destination.path != "/api/v1/telegram/webhook"
    ):
        parser.error("Expected a public HTTPS URL for /api/v1/telegram/webhook")
    token, secret = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_WEBHOOK_SECRET
    if not token or not secret:
        parser.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first")
    try:
        result = requests.post(
            f"https://api.telegram.org/bot{token.get_secret_value()}/setWebhook",
            json={
                "url": url,
                "secret_token": secret.get_secret_value(),
                "allowed_updates": ["message"],
            },
            timeout=10,
            allow_redirects=False,
        )
        ok = result.status_code == 200 and result.json().get("ok") is True
    except (requests.RequestException, ValueError):
        raise SystemExit("Could not contact Telegram") from None
    if not ok:
        raise SystemExit(f"Telegram rejected setWebhook (HTTP {result.status_code})")
    print("Webhook registered.")


if __name__ == "__main__":
    main()
