# -*- coding: utf-8 -*-
"""استارت Tor به‌صورت خودکار داخل بات (اگر نصب بود و اجرا نبود)
این تابع را در main() صدا می‌زنیم — دیگر وابسته به start.sh نیستیم"""
import os
import shutil
import socket
import subprocess
import time


def ensure_tor_running():
    """Tor را شروع کن اگر نصب است و SOCKS5 ندارد"""
    if not shutil.which("tor"):
        print("[tor] not installed — running without proxy")
        return False

    # از قبل زنده است؟
    try:
        s = socket.create_connection(("127.0.0.1", 9050), timeout=2)
        s.close()
        print("[tor] already running on 9050")
        return True
    except OSError:
        pass

    # torrc مناسب پیدا/بساز
    for cand in ["/etc/tor/torrc-zerox", "/tmp/torrc", "torrc"]:
        if os.path.exists(cand):
            torrc = cand
            break
    else:
        torrc = "/tmp/torrc-zerox"
        os.makedirs("/tmp/tor_data", exist_ok=True)
        open(torrc, "w").write(
            "SocksPort 9050\n"
            "ControlPort 9051\n"
            "DataDirectory /tmp/tor_data\n"
            "CookieAuthentication 1\n"
            "ExitNodes {us},{nl},{de},{fr},{tr}\n"
            "StrictNodes 0\n"
            "MaxCircuitDirtiness 300\n"
            "UseBridges 0\n"
            "Log notice file /tmp/tor_data/tor.log\n"
        )

    print("[tor] starting in background...")
    subprocess.Popen(
        ["tor", "-f", torrc],
        stdout=open("/tmp/tor_stdout.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # صبر کوتاه تا SOCKS باز شود (حداکثر 30 ثانیه — بات را بلاک نکنیم)
    for _ in range(30):
        time.sleep(1)
        try:
            s = socket.create_connection(("127.0.0.1", 9050), timeout=2)
            s.close()
            print("[tor] SOCKS5 up on 9050 — YouTube traffic will use Tor")
            return True
        except OSError:
            continue
    print("[tor] did not start in 30s — bot continues without proxy")
    return False
