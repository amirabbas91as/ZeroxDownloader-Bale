# 📥 ZeroxDownloader برای بله (Bale)

نسخه بله‌ی بات دانلودر ZeroxDownloader — یوتیوب / اسپاتیفای / تیک‌تاک داخل بله.

## تفاوت با نسخه تلگرام

همان امکانات، فقط برای **پیام‌رسان بله** — از Bot API بله (`tapi.bale.ai`) استفاده می‌کند.

## اجرا

```bash
pip install -r requirements.txt
export BOT_TOKEN="توکن بات از @BotFather بله"
python3 bot.py
```

## ساخت بات در بله

1. در بله به [BotFather بله](https://ble.ir/BotFather) پیام بده
2. `/newbot` — نام و نام کاربری بات را انتخاب کن
3. توکن را کپی و در متغیر `BOT_TOKEN` بگذار

## دستورات

| دستور | کار |
|-------|-----|
| `/start` | شروع و راهنما |
| `/song` | لینک بعدی به‌صورت MP3 |
| `/video` | لینک بعدی به‌صورت ویدیو |
| `/videobox 480` | تغییر کیفیت ویدیوی یوتیوب |

## معماری

```
bot.py           بات اصلی (API بله از طریق bale_compat)
bale_compat.py   لایه سازگاری — python-telegram-bot را به بله وصل می‌کند
retry_helper.py  تلاش مجدد برای بلاک‌های موقت یوتیوب
```

## نکته یوتیوب

بات به‌طور پیش‌فرض از Tor استفاده می‌کند (`socks5h://127.0.0.1:9050`) تا بلاک IP دیتاسنتر دور زده شود. اگر Tor روی سرورت نصب نیست:

```bash
apt install tor
tor -f /tmp/tor_test/torrc &   # یا torrc دلخواه
```

برای غیرفعال کردن: `export TOR_ENABLED=0`
