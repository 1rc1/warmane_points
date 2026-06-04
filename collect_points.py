#!/usr/bin/env python3
"""Collect daily Warmane coinage points.

The Warmane login form is protected by an interactive Cloudflare Turnstile
challenge ("Verify you are human"), so a plain HTTP login is rejected by the
server. We drive a real (headed, under Xvfb) Chromium browser via patchright —
a patched Playwright that evades automation detection — to fill the form, click
the Turnstile checkbox, and obtain the token. Once logged in, the session
cookies are handed to `requests` for the actual points collection.
"""

import os
import sys
import logging
import tempfile

import requests
from bs4 import BeautifulSoup
from patchright.sync_api import sync_playwright, TimeoutError as PWTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE = "https://www.warmane.com"
ACCOUNT_URL = f"{BASE}/account"
LOGIN_URL = f"{BASE}/account/login"
TURNSTILE_IFRAME = "iframe[src*='challenges.cloudflare.com']"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

# Headed by default — Turnstile only issues a token to a non-headless browser.
# Requires an X display (the Docker image runs Xvfb; see entrypoint.sh).
HEADLESS = os.environ.get("WARMANE_HEADLESS", "false").lower() == "true"
# Max wait (ms) for Turnstile to issue its token after the checkbox is clicked.
TURNSTILE_TIMEOUT = int(os.environ.get("WARMANE_TURNSTILE_TIMEOUT", "45000"))

_TOKEN_READY_JS = (
    "() => { const e = document.querySelector('[name=\"cf-turnstile-response\"]');"
    " return e && e.value && e.value.length > 20; }"
)


def _solve_turnstile(page, name: str, attempts: int = 3) -> bool:
    """Load the login page and clear the interactive Turnstile challenge.

    Clicks the "Verify you are human" checkbox inside the Cloudflare iframe and
    waits for the token to land in the hidden form field. Turnstile is flaky,
    so this reloads and retries a few times. Returns True once a token exists.
    """
    for attempt in range(1, attempts + 1):
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            # The widget needs a moment to initialise — clicking before its JS
            # is ready registers on a dead widget and no token is ever issued.
            # (Don't wait_for_selector on the iframe: Cloudflare's iframe is
            # reported non-visible, so a visibility wait just burns the timeout.
            # The frame_locator click below auto-waits for the checkbox itself.)
            page.wait_for_timeout(6000)
            page.frame_locator(TURNSTILE_IFRAME).locator(
                "input[type=checkbox]"
            ).click(timeout=15000)
            page.wait_for_function(_TOKEN_READY_JS, timeout=TURNSTILE_TIMEOUT)
            return True
        except PWTimeout:
            log.warning(
                "[%s] Turnstile attempt %d/%d did not yield a token; retrying",
                name, attempt, attempts,
            )
    log.error(
        "[%s] Turnstile did not issue a token after %d attempts — the captcha "
        "challenge failed (often IP reputation; try a residential network)",
        name, attempts,
    )
    return False


def browser_login(name: str, username: str, password: str):
    """Log in through a real browser, solving the Turnstile challenge.

    Returns (cookies, csrf, page_html) on success, or (None, None, None) on
    failure. `cookies` is the list of Playwright cookie dicts for the
    authenticated session.
    """
    with sync_playwright() as p, tempfile.TemporaryDirectory(prefix="wm-udd-") as udd:
        # patchright works best with a persistent context + the real Chromium
        # channel; that combination is what gets past Cloudflare's detection.
        # NOTE: do not override user_agent or pass detectable args here.
        # patchright relies on the browser's genuine fingerprint; a spoofed UA
        # creates a mismatch that makes Cloudflare refuse to issue a token.
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=udd,
            channel="chromium",
            headless=HEADLESS,
            no_viewport=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = ctx.new_page()
        try:
            # Solve the Turnstile challenge first (it's flaky, so retry), then
            # fill credentials. This mirrors the sequence that reliably gets a
            # token; touching the form fields first can disturb the widget.
            if not _solve_turnstile(page, name):
                return None, None, None

            page.fill("#userID", username)
            page.fill("#userPW", password)

            # The form submits via AJAX; wait for the login POST to complete.
            try:
                with page.expect_response(
                    lambda r: "/account/login" in r.url
                    and r.request.method == "POST",
                    timeout=60000,
                ) as resp_info:
                    page.click("button[type=submit]")
                # Best-effort: log the response body. On a successful login the
                # browser redirects and evicts the body, so reading it may fail
                # — that's fine, it's only informational.
                try:
                    log.info("[%s] Login response: %s", name, resp_info.value.text()[:200])
                except Exception:
                    pass
            except PWTimeout:
                log.error("[%s] Login request never completed", name)
                return None, None, None

            # Confirm authentication and grab the CSRF token.
            page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=60000)
            if "/account/login" in page.url:
                log.error(
                    "[%s] Login failed — check WARMANE_USERNAME_%s / "
                    "WARMANE_PASSWORD_%s (or 2FA)",
                    name, name, name,
                )
                return None, None, None

            csrf = None
            meta = page.query_selector("meta[name=csrf-token]")
            if meta:
                csrf = meta.get_attribute("content")

            cookies = ctx.cookies()
            page_html = page.content()
            return cookies, csrf, page_html
        finally:
            ctx.close()


def collect_for_account(name: str, username: str, password: str) -> bool:
    cookies, csrf, page_html = browser_login(name, username, password)
    if cookies is None:
        return False

    soup = BeautifulSoup(page_html, "lxml")

    points_el = soup.find("span", class_="myPoints")
    log.info("[%s] Logged in (current points: %s)",
             name, points_el.get_text(strip=True) if points_el else "?")

    collect_link = soup.find("a", attrs={"data-click": "collectpoints"})
    if not collect_link:
        log.info("[%s] Points already collected today (collect link not present)", name)
        return True

    # Carry the browser's authenticated session into requests for the collect POST.
    session = requests.Session()
    session.headers.update(HEADERS)
    for c in cookies:
        session.cookies.set(
            c["name"], c["value"],
            domain=c["domain"].lstrip("."),
            path=c.get("path", "/"),
        )

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

    msgs = data.get("messages", {})
    errors = msgs.get("error", [])
    if errors:
        log.error("[%s] Server error: %s", name, "; ".join(errors))
        return False

    log.warning("[%s] Unexpected response: %s", name, data)
    return False


def get_accounts() -> list[tuple[str, str, str]]:
    accounts = []
    i = 1
    while True:
        username = os.environ.get(f"WARMANE_USERNAME_{i}", "").strip()
        password = os.environ.get(f"WARMANE_PASSWORD_{i}", "").strip()
        if not username or not password:
            break
        label = os.environ.get(f"WARMANE_NAME_{i}", username).strip()
        accounts.append((label, username, password))
        i += 1
    return accounts


def collect():
    accounts = get_accounts()
    if not accounts:
        log.error(
            "No accounts configured. Add to .env:\n"
            "  WARMANE_USERNAME_1=myusername\n"
            "  WARMANE_PASSWORD_1=mypassword\n"
            "  WARMANE_NAME_1=MyAccount  (optional label)"
        )
        sys.exit(1)

    log.info("Processing %d account(s)", len(accounts))
    failed = []
    for name, username, password in accounts:
        try:
            ok = collect_for_account(name, username, password)
        except Exception:
            log.exception("[%s] Unexpected error during collection", name)
            ok = False
        if not ok:
            failed.append(name)

    if failed:
        log.error("Collection failed for: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    collect()
