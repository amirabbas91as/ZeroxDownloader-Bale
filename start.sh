#!/bin/bash
# راه‌اندازی سریع Tor (بدون بلاک کردن) + بات بله
tor -f /etc/tor/torrc-zerox > /tmp/tor.log 2>&1 &
disown
exec python3 bot.py
