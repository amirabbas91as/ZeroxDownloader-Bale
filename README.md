# 📥 ZeroxDownloader برای بله (Bale)

بات دانلودر بله — یوتیوب / اسپاتیفای / تیک‌تاک.

## دیپلوی روی Railway

**ریپو را وصل کن — Railway خودش Dockerfile را build می‌کند:**
- Tor + **obfs4proxy** + ffmpeg داخل کانتینر نصب می‌شوند
- `start.sh` اول Tor را بک‌گراند اجرا می‌کند و بلافاصله بات را استارت می‌کند
- بات موقع هر دانلود چک می‌کند Tor زنده است؛ اگر بلاک شد مدار می‌چرخاند (NEWNYM)
- متغیر محیطی: `BOT_TOKEN`

**نکته:** در Railway مطمئن شو **Start Command خالی است** تا Dockerfile CMD (`start.sh`) اجرا شود.

## نکته مهم: بریج‌های obfs4

یوتیوب بعضی رله‌های Tor را بلاک کرده. `torrc` شامل **بریج‌های obfs4** است که ترافیک Tor را پشت ترافیک عادی HTTPS مخفی می‌کنند تا از Railway عبور کند.

## اجرا محلی

```bash
apt install tor ffmpeg obfs4proxy
pip install -r requirements.txt
export BOT_TOKEN="توکن از BotFather بله"
python3 bot.py
```

## دستورات

| دستور | کار |
|-------|-----|
| `/start` | راهنما |
| `/song` | لینک بعدی → MP3 |
| `/video` | لینک بعدی → ویدیو |
| `/videobox 480` | کیفیت یوتیوب |

تیک‌تاک همیشه مستقیم و بدون مشکل کار می‌کند.
