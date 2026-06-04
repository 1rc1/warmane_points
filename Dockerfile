# Official Playwright image — ships Chromium's system dependencies and Xvfb,
# which are exactly the painful parts to install otherwise.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# DISPLAY for the Xvfb server started by entrypoint.sh (also inherited by
# `docker compose exec` runs).
ENV DISPLAY=:99

# Install supercronic (lightweight cron for containers)
ADD https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patched Chromium used by patchright to evade Cloudflare's bot detection.
RUN patchright install chromium

COPY collect_points.py crontab entrypoint.sh ./
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
