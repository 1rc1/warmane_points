#!/usr/bin/env bash
# Start a virtual X display so headed Chromium (needed to pass Cloudflare
# Turnstile) has somewhere to render, then hand off to supercronic.
set -e

Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &

# Wait for the X socket to appear before starting the cron runner.
for _ in $(seq 1 30); do
    [ -S /tmp/.X11-unix/X99 ] && break
    sleep 0.3
done

exec supercronic /app/crontab
