FROM python:3.11-slim

# Tor + obfs4proxy + ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends tor ffmpeg obfs4proxy && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# torrc با بریج‌های obfs4
RUN mkdir -p /tmp/tor_data && cp torrc /etc/tor/torrc-zerox

EXPOSE 8080

CMD ["bash", "start.sh"]
