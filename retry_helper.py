# -*- coding: utf-8 -*-
"""Retry logic برای بلاک متناوب یوتیوب:
وقتی Sign in to confirm آمد، تا ۳ بار با فاصله ۲۰ ثانیه دوباره امتحان کن
(چون بلاک متناوبه، گاهی دفعه دوم درست می‌شود)"""
import time

import yt_dlp


def retry_download(func, *args, max_retries=3, delay=15, **kwargs):
    """اجرای تابع دانلود با retry - برای خطاهای موقتی یوتیوب"""
    last_err = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err = str(e)
            retryable = ("Sign in to confirm" in err or
                         "needs to be reloaded" in err or
                         "Requested format is not available" in err)
            if not retryable or attempt == max_retries - 1:
                raise
            last_err = e
            print(f"  retry {attempt + 1}/{max_retries} after {delay}s...")
            time.sleep(delay)
    raise last_err
