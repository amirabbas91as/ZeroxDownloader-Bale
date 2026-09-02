FROM python:3.11-slim

# Tor + وابستگی‌های سیستمی
RUN apt-get update && \
    apt-get install -y --no-install-recommends tor ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# torrc را جای استاندارد کپی کن
RUN mkdir -p /tmp/tor_data && cp torrc /etc/tor/torrc-zerox

EXPOSE 8080

CMD ["bash", "start.sh"]
