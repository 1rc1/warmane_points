#!/usr/bin/env python3
"""Collect daily Warmane coinage points."""

import os
import sys
import logging
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE = "https://www.warmane.com"
ACCOUNT_URL = f"{BASE}/account"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def make_session(cookie_str: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            session.cookies.set(name.strip(), value.strip(), domain="www.warmane.com")
    return session


def get_account_page(session: requests.Session, name: str):
    """Fetch the account page. Returns (soup, csrf_token) or exits on auth failure."""
    r = session.get(ACCOUNT_URL)
    r.raise_for_status()

    if "/account/login" in r.url:
        log.error(
            "[%s] Cookie expired — log into warmane.com, open DevTools → Network → "
            "any request → Request Headers → copy the full Cookie value into .env",
            name,
        )
        return None, None

    soup = BeautifulSoup(r.text, "lxml")

    meta = soup.find("meta", {"name": "csrf-token"})
    csrf = meta["content"] if meta else None

    log.info("[%s] Session valid (current points: %s)",
             name, (soup.find("span", class_="myPoints") or {}).get_text(strip=True) or "?")
    return soup, csrf


def collect_for_account(name: str, cookie_str: str) -> bool:
    session = make_session(cookie_str)
    soup, csrf = get_account_page(session, name)
    if soup is None:
        return False

    # Check if the collect link is present (hidden after already collecting today)
    collect_link = soup.find("a", attrs={"data-click": "collectpoints"})
    if not collect_link:
        log.info("[%s] Points already collected today (collect link not present)", name)
        return True

    # Mirror exactly what the browser JS does:
    #   POST /account  data={collectpoints: true}  with CSRF token
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": ACCOUNT_URL}
    if csrf:
        headers["X-CSRF-TOKEN"] = csrf

    r = session.post(
        ACCOUNT_URL,
        data={"collectpoints": "true", "_token": csrf} if csrf else {"collectpoints": "true"},
        headers=headers,
    )
    r.raise_for_status()

    log.info("[%s] POST response (HTTP %s): %s", name, r.status_code, r.text[:300])

    try:
        data = r.json()
    except ValueError:
        log.error("[%s] Non-JSON response — something went wrong", name)
        return False

    if data.get("points") is not None:
        log.info("[%s] Points collected — new balance: %s", name, data["points"])
        return True

    # Server may return error messages
    msgs = data.get("messages", {})
    errors = msgs.get("error", [])
    if errors:
        log.error("[%s] Server error: %s", name, "; ".join(errors))
        return False

    log.warning("[%s] Unexpected response: %s", name, data)
    return False


def get_accounts() -> list[tuple[str, str]]:
    accounts = []
    i = 1
    while True:
        label = os.environ.get(f"WARMANE_NAME_{i}", str(i)).strip()
        cookie = os.environ.get(f"WARMANE_COOKIE_{i}", "").strip()
        if not cookie:
            break
        accounts.append((label, cookie))
        i += 1
    return accounts


def collect():
    accounts = get_accounts()
    if not accounts:
        log.error(
            "No accounts configured. Add to .env:\n"
            "  WARMANE_NAME_1=MyAccount\n"
            "  WARMANE_COOKIE_1=<full Cookie header from browser DevTools>"
        )
        sys.exit(1)

    log.info("Processing %d account(s)", len(accounts))
    failed = []
    for name, cookie in accounts:
        if not collect_for_account(name, cookie):
            failed.append(name)

    if failed:
        log.error("Collection failed for: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    collect()
