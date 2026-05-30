FROM python:3.12-slim

WORKDIR /app

# Install supercronic (lightweight cron for containers)
ADD https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collect_points.py .
COPY crontab .

CMD ["supercronic", "/app/crontab"]
