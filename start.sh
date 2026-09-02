#!/bin/bash
# راه‌اندازی Tor و بعد بات
set -e

echo "🧅 Starting Tor..."
tor -f /etc/tor/torrc-zerox &
TOR_PID=$!

# صبر تا Tor بوت‌استرپ شود (حداکثر 90 ثانیه)
echo "⏳ Waiting for Tor bootstrap..."
for i in $(seq 1 90); do
  if sleep 1; then
    # چک: آیا SOCKS port باز شده؟
    if python3 -c "
import socket, sys
try:
    s = socket.create_connection(('127.0.0.1', 9050), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      echo "✅ Tor SOCKS5 is up on port 9050"
      break
    fi
  fi
  if [ $i -eq 90 ]; then
    echo "⚠️ Tor did not bootstrap in 90s — running bot without proxy"
  fi
done

echo "🤖 Starting Bale bot..."
exec python3 bot.py
