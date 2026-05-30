# Warmane Daily Points Collector

Automatically collects daily coinage points on [Warmane](https://www.warmane.com) for up to 20 accounts. Runs in Docker on a daily cron schedule.

## Requirements

- Docker + Docker Compose

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/1rc1/warmane_points.git
cd warmane_points
```

### 2. Get your session cookie

1. Open Chrome/Firefox and log into [warmane.com/account](https://www.warmane.com/account)
2. Press **F12** → **Network** tab
3. Click any request to `www.warmane.com` in the list
4. In the right panel open **Request Headers**
5. Find the `Cookie:` line and copy everything after `Cookie: `

**For multiple accounts** — get each cookie without logging out:
- Use a **private/incognito window** for the second account (separate session from your main browser)
- Or use a second **browser profile** (each profile has its own independent session)

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your accounts:

```env
WARMANE_NAME_1=MyAccount
WARMANE_COOKIE_1=PHPSESSID=abc123...; other=value...

WARMANE_NAME_2=AnotherAccount
WARMANE_COOKIE_2=PHPSESSID=xyz456...; other=value...
```

Supports up to 20 accounts — just keep adding numbered blocks.

### 4. Start the container

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

## Cookie expiry

Cookies typically last several weeks. When one expires the script logs:

```
[AccountName] Cookie expired — log into warmane.com, open DevTools → Network → ...
```

Just repeat step 2 above and update the cookie in your `.env`, then restart:

```bash
docker compose restart
```
