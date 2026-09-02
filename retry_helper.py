# -*- coding: utf-8 -*-
"""تشخیص Tor - کش نتیجه تا هر ۳۰ ثانیه یک‌بار چک شود (سرعت بالاتر)"""
import glob
import os
import socket
import time

_cache = {"ts": 0, "socks": False, "cookie": None}


def _find_tor():
    """Tor SOCKS5 و ControlPort - با کش ۳۰ ثانیه‌ای"""
    now = time.time()
    if now - _cache["ts"] < 30:
        return _cache["socks"], _cache["cookie"]

    socks = False
    cookie = None
    try:
        s = socket.create_connection(("127.0.0.1", 9050), timeout=2)
        s.close()
        socks = True
    except OSError:
        pass

    for pattern in [
        "/var/lib/tor/nekate/control_auth_cookie",
        "/tmp/tor_data/control_auth_cookie",
        "/var/lib/tor/control_auth_cookie",
    ] + glob.glob("/tmp/tor_data*/control_auth_cookie"):
        if os.path.exists(pattern):
            cookie = pattern
            break

    _cache.update(ts=now, socks=socks, cookie=cookie)
    return socks, cookie


def _tor_alive():
    socks, _ = _find_tor()
    return socks


def rotate_tor_circuit():
    """سیگنال NEWNYM - مدار خروجی جدید Tor"""
    socks, cookie_path = _find_tor()
    if not socks or not cookie_path:
        return False
    try:
        cookie = open(cookie_path, "rb").read()
        s = socket.create_connection(("127.0.0.1", 9051), timeout=10)
        s.sendall(b"AUTHENTICATE " + cookie.hex().encode() + b"\r\n")
        time.sleep(0.3)
        s.recv(256)
        s.sendall(b"SIGNAL NEWNYM\r\n")
        time.sleep(0.3)
        s.recv(256)
        s.close()
        time.sleep(8)
        _cache["ts"] = 0  # کش را باطل کن
        return True
    except Exception as e:
        print(f"tor rotate failed: {e}")
        return False


def retry_with_rotation(func, *args, max_retries=4, **kwargs):
    """دانلود با retry - اگر Tor بود مدار بچرخان، وگرنه صبر ساده"""
    last_err = None
    has_tor = _tor_alive()
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err = str(e)
            retryable = ("Sign in to confirm" in err or
                         "needs to be reloaded" in err or
                         "Requested format" in err)
            if not retryable or attempt == max_retries - 1:
                raise
            last_err = e
            if has_tor:
                print(f"  blocked, rotating Tor circuit ({attempt+1}/{max_retries})...")
                rotate_tor_circuit()
            else:
                print(f"  blocked, simple retry ({attempt+1}/{max_retries})...")
                time.sleep(10)
    raise last_err
