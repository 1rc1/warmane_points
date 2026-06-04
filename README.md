# Warmane Daily Points Collector

Automatically collects daily coinage points on [Warmane](https://www.warmane.com) for up to 20 accounts. Runs in Docker on a daily cron schedule.

The login form is protected by an interactive Cloudflare Turnstile challenge ("Verify you are human"). The collector logs in by driving a real Chromium browser (headed, under a virtual X display) via [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) — a patched Playwright that evades bot detection — clicking the Turnstile checkbox to obtain a token. It then collects points for each account using your username and password — no manual cookie copying required.

## Requirements

- Docker + Docker Compose

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/1rc1/warmane_points.git
cd warmane_points
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your accounts:

```env
WARMANE_USERNAME_1=myusername
WARMANE_PASSWORD_1=mypassword

WARMANE_USERNAME_2=anotheruser
WARMANE_PASSWORD_2=anotherpassword
```

Supports up to 20 accounts; just keep adding numbered blocks. Optionally set `WARMANE_NAME_N` to label an account in the logs (defaults to the username).

### 3. Start the container

```bash
docker compose up -d --build
```

Points are collected automatically every day at **23:00 UTC**.

## Usage

**Check logs:**
```bash
docker compose logs -f
```

**Run manually (test it now):**
```bash
docker compose exec warmane-points python collect_points.py
```

**Stop:**
```bash
docker compose down
```

## Optional tuning

These environment variables can be set in `.env`:

- `WARMANE_TURNSTILE_TIMEOUT=45000` — how long (ms) to wait for Turnstile to issue its token after clicking the checkbox.
- `WARMANE_HEADLESS=true` — run Chromium headless. **Not recommended** — Cloudflare typically refuses to issue a token to a headless browser. The default (headed, under the container's Xvfb display) is what works.

## Troubleshooting

**`Login failed — check WARMANE_USERNAME_N / WARMANE_PASSWORD_N`**
The credentials were rejected (or the account uses two-factor auth). Double-check the username and password in `.env`.

**`Turnstile did not issue a token in time — the captcha challenge failed`**
Cloudflare didn't hand over a token. This is usually about IP reputation — datacenter/VPS IPs get harsher challenges than home connections. Try increasing `WARMANE_TURNSTILE_TIMEOUT`, or run the container from a residential network.
