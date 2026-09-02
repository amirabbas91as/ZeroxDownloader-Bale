# -*- coding: utf-8 -*-
"""راه‌حل نهایی: اگر اولین دانلود بلاک شد، مدار Tor را عوض کن و دوباره امتحان کن
این helper داخل بات استفاده می‌شود - تا ۶ بار مدار می‌چرخاند"""
import socket
import time


def rotate_tor_circuit():
    """سیگنال NEWNYM به Tor ControlPort - مدار خروجی جدید می‌سازد"""
    try:
        cookie = open("/var/lib/tor/nekate/control_auth_cookie", "rb").read()
        s = socket.create_connection(("127.0.0.1", 9051), timeout=10)
        s.sendall(b"AUTHENTICATE " + cookie.hex().encode() + b"\r\n")
        time.sleep(0.3)
        s.recv(256)
        s.sendall(b"SIGNAL NEWNYM\r\n")
        time.sleep(0.3)
        s.recv(256)
        s.close()
        time.sleep(10)  # صبر برای مدار جدید
        return True
    except Exception as e:
        print(f"tor rotate failed: {e}")
        return False


def retry_with_rotation(func, *args, max_retries=4, **kwargs):
    """اجرای تابع دانلود - اگر بلاک شد مدار Tor عوض کن و دوباره"""
    last_err = None
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
            print(f"  blocked, rotating Tor circuit ({attempt+1}/{max_retries})...")
            rotate_tor_circuit()
    raise last_err
