# -*- coding: utf-8 -*-
# بات دانلودر بله - یوتیوب / اسپاتیفای / تیک‌تاک
# اجرا: BOT_TOKEN=... python3 bot.py
import asyncio
import logging
import os
import re
import tempfile
import time
import uuid

import requests
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import yt_dlp

from bale_compat import create_bale_app
from retry_helper import retry_with_rotation as retry_download

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger("downloader-bot")

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/tg_bot_downloads")
MAX_TG_SIZE = 49 * 1024 * 1024  # محدودیت آپلود بات تلگرام (49MB)
TOR_ENABLED = os.environ.get("TOR_ENABLED", "1") == "1"  # پیش‌فرض روشن
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------- تشخیص پلتفرم

YOUTUBE_RE = re.compile(
    r"(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)", re.I
)
SPOTIFY_RE = re.compile(
    r"(open\.)?spotify\.com/(track|album|playlist)/", re.I
)
SPOTIFY_KIND_RE = re.compile(r"spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)", re.I)
TIKTOK_RE = re.compile(r"(tiktok\.com/@[\w.-]+/video/|vm\.tiktok\.com/|vt\.tiktok\.com/)", re.I)


def detect_platform(url: str):
    if YOUTUBE_RE.search(url):
        return "youtube"
    if SPOTIFY_RE.search(url):
        return "spotify"
    if TIKTOK_RE.search(url):
        return "tiktok"
    return None


def extract_url(text: str):
    m = re.search(r"https?://\S+", text)
    return m.group(0).rstrip(").,،") if m else None


# ---------------------------------------------------------------- دانلود

def yt_common_opts():
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        "retries": 5,
        "concurrent_fragment_downloads": 4,
    }
    # Tor proxy برای دور زدن بلاک یوتیوب روی IP دیتاسنتر
    if os.path.exists("/var/lib/tor/nekate") or TOR_ENABLED:
        opts["proxy"] = "socks5h://127.0.0.1:9050"
    # پشتیبانی از cookies برای دور زدن بات‌چک یوتیوب روی IP سرور
    cookies_file = os.environ.get("YOUTUBE_COOKIES", "cookies.txt")
    if os.path.exists(cookies_file):
        opts["cookiefile"] = cookies_file
    return opts


BOT_CHECK_MSG = (
    "❌ یوتیوب موقتاً این سرور را بلاک کرده.\n\n"
    "این بلاک موقتیه — چند ساعت دیگه خودش باز می‌شه.\n\n"
    "▶️ تیک‌تاک الان کار می‌کنه ✅\n"
    "▶️ اسپاتیفای: متادیتا می‌خونه ولی دانلود نهایی از یوتیوب است\n\n"
    "💡 برای دانلود بدون وقفه، بات را روی سیستم خودت اجرا کن — "
    "سورس کامل روی گیت‌هاب هست (github.com/amirabbas91as/ZeroxDownloader)"
)


def download_video(url: str, platform: str, max_height: int = 720):
    """دانلود ویدیو (یوتیوب/تیک‌تاک) - خروجی mp4"""
    outtmpl = os.path.join(DOWNLOAD_DIR, f"vid_{uuid.uuid4().hex[:10]}.%(ext)s")
    opts = yt_common_opts()
    if platform == "youtube":
        opts.update({
            # ویدیو<=max_height + بهترین صدا، ادغام با ffmpeg
            "format": (
                f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_height}]+bestaudio/"
                f"best[height<={max_height}]/best"
            ),
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        })
    else:  # tiktok - بدون واترمارک
        opts.update({
            "format": "best[ext=mp4]/best",
            "outtmpl": outtmpl,
        })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        # اگر merge شد ممکن است ext عوض شده باشد
        if not os.path.exists(filepath):
            base = os.path.splitext(filepath)[0]
            for ext in (".mp4", ".mkv", ".webm"):
                if os.path.exists(base + ext):
                    filepath = base + ext
                    break
    return {
        "path": filepath,
        "title": info.get("title") or "video",
        "duration": int(info.get("duration") or 0),
        "uploader": info.get("uploader") or info.get("channel") or "",
    }


def search_youtube_by_title(query: str, target_duration: int = 0):
    """جستجوی عنوان در یوتیوب - برای لینک اسپاتیفای.
    target_duration: طول ترک اصلی به ثانیه - نتایج خیلی بلندتر (مثل 1 HOUR) رد می‌شوند"""
    opts = yt_common_opts()
    opts.update({
        "format": "bestaudio/best",
        "default_search": "ytsearch5",
        "extract_flat": False,
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        entries = info.get("entries") or []
        if not entries:
            return None
        # اگر duration هدف داریم، بهترین تطابق را انتخاب کن
        if target_duration > 0:
            best = None
            best_score = None
            for e in entries:
                dur = e.get("duration") or 0
                if dur <= 0:
                    continue
                # ویدیوهای خیلی بلند (بیش از ۱.۵ برابر + ۹۰ ثانیه) رد شوند
                if dur > target_duration * 1.5 + 90:
                    continue
                diff = abs(dur - target_duration)
                if best_score is None or diff < best_score:
                    best = e
                    best_score = diff
            if best:
                return best
            # هیچ نتیجه‌ای در محدوده نبود - کوتاه‌ترین را بده
            valid = [e for e in entries if (e.get("duration") or 0) > 0]
            return min(valid, key=lambda e: e.get("duration")) if valid else entries[0]
        return entries[0]


def _embed_cover(filepath: str, cover_url: str):
    """دانلود کاور و جاسازی در MP3 به‌عنوان artwork"""
    if not cover_url:
        return False
    try:
        import requests
        r = requests.get(cover_url, timeout=30)
        r.raise_for_status()
        img_data = r.content
        # بررسی فرمت - mutagen jpg/png می‌پذیرد
        if not img_data[:3] == b"\xff\xd8\xff" and not img_data[:8].startswith(b"\x89PNG"):
            log.warning("cover: not jpg/png (%s...)", img_data[:8].hex())
            return False

        audio = MP3(filepath, ID3=EasyID3)
        try:
            audio.add_tags()  # اگر ID3 نبود اضافه کن
        except Exception:
            pass  # از قبل هست
        from mutagen.id3 import ID3, APIC
        id3 = ID3(filepath)
        # کاور قبلی را پاک کن
        id3.delall("APIC")
        mime = "image/jpeg" if img_data[:3] == b"\xff\xd8\xff" else "image/png"
        id3.add(APIC(
            encoding=3,
            mime=mime,
            type=3,  # front cover
            desc="Cover",
            data=img_data,
        ))
        id3.save()
        return True
    except Exception as e:
        log.warning("cover embed failed: %s", e)
        return False


def download_audio_mp3(url: str, title_hint: str = "", artist: str = "",
                       thumbnail: str = ""):
    """دانلود و تبدیل به MP3 با تگ‌های کامل + کاور"""
    outtmpl = os.path.join(DOWNLOAD_DIR, f"aud_{uuid.uuid4().hex[:10]}.%(ext)s")
    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        },
        {"key": "FFmpegMetadata"},
    ]
    opts = yt_common_opts()
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": postprocessors,
    })
    if title_hint:
        opts["postprocessor_args"] = {
            "FFmpegExtractAudio": [
                "-metadata", f"title={title_hint}",
                "-metadata", f"artist={artist or 'Unknown'}",
            ]
        }
    cover_url = thumbnail
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        base = os.path.splitext(filepath)[0] + ".mp3"
        if os.path.exists(base):
            filepath = base
    # تگ‌گذاری نهایی با mutagen
    try:
        audio = MP3(filepath, ID3=EasyID3)
        if title_hint:
            audio["title"] = title_hint
        if artist:
            audio["artist"] = artist
        audio["album"] = "ZeroxDownloader"
        audio.save()
    except Exception as e:
        log.warning("tagging failed: %s", e)

    # کاور: اولویت با کاور اسپاتیفای، بعد thumbnail خود یوتیوب
    cover_applied = False
    if not cover_url:
        cover_url = info.get("thumbnail") or ""
    if cover_url:
        cover_applied = _embed_cover(filepath, cover_url)
    if not cover_applied:
        # fallback: thumbnail یوتیوب با بالاترین کیفیت (maxres)
        try:
            vid_id = info.get("id") or ""
            if vid_id:
                from mutagen.id3 import ID3, APIC
                for quality in ["maxresdefault", "hqdefault"]:
                    turl = f"https://i.ytimg.com/vi/{vid_id}/{quality}.jpg"
                    tdata = requests.get(turl, timeout=30).content
                    if len(tdata) > 5000:  # maxres معمولا موجود است
                        id3 = ID3(filepath)
                        id3.delall("APIC")
                        id3.add(APIC(encoding=3, mime="image/jpeg", type=3,
                                     desc="Cover", data=tdata))
                        id3.save()
                        cover_applied = True
                        break
        except Exception as e:
            log.warning("thumbnail embed fallback failed: %s", e)

    return {
        "path": filepath,
        "title": title_hint or info.get("title") or "audio",
        "duration": int(info.get("duration") or 0),
        "performer": artist or (info.get("uploader") or ""),
        "cover": cover_url or "",
        "has_cover": cover_applied,
    }


# ---------------------------------------------------------------- اسپاتیفای

def _spotify_embed_entity(kind: str, item_id: str):
    """entity صفحه embed اسپاتیفای (track/album/playlist) یا None"""
    import json as _json
    try:
        r = requests.get(
            f"https://open.spotify.com/embed/{kind}/{item_id}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            timeout=20,
        )
        m2 = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text, re.S,
        )
        if not m2:
            return None
        props = _json.loads(m2.group(1))["props"]["pageProps"]
        if "state" not in props:
            return None
        return props["state"]["data"].get("entity")
    except Exception as e:
        log.warning("spotify embed failed: %s", e)
        return None


def spotify_tracks(url: str):
    """لیست ترک‌های یک لینک اسپاتیفای (track = 1 آیتم، album/playlist = همه).
    خروجی: لیست دیکشنری [{title, artist, duration, cover}]"""
    m = SPOTIFY_KIND_RE.search(url)
    if not m:
        return []
    kind, item_id = m.group(1).lower(), m.group(2)

    entity = _spotify_embed_entity(kind, item_id)
    if not entity:
        return []

    if kind == "track":
        artists = [a.get("name", "") for a in entity.get("artists", [])]
        # کاور 640x640 از صفحه کامل ترک (prefix بزرگ)
        cover = _spotify_big_cover("track", item_id)
        return [{
            "title": entity.get("title") or entity.get("name", ""),
            "artist": ", ".join(a for a in artists if a),
            "duration": int((entity.get("duration") or 0) / 1000),
            "cover": cover,
        }]

    # album / playlist - entity خودش trackList دارد
    album_name = entity.get("title") or ""
    album_artist = entity.get("subtitle") or ""
    # کاور بزرگ آلبوم/پلی‌لیست
    album_cover = _spotify_big_cover(kind, item_id)
    tracks = []
    for t in entity.get("trackList", []):
        tid = (t.get("uri") or "").split(":")[-1]
        tracks.append({
            "title": t.get("title", ""),
            "artist": t.get("subtitle") or album_artist,
            "duration": int((t.get("duration") or 0) / 1000),
            "cover": album_cover,
            "id": tid,
        })
    return tracks


def _spotify_big_cover(kind: str, item_id: str):
    """استخراج کاور 640x640 (prefix ab67616d0000b273) از صفحه کامل اسپاتیفای"""
    try:
        r = requests.get(
            f"https://open.spotify.com/{kind}/{item_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=20,
        )
        # کاور مربع بزرگ
        m = re.search(
            r'(https://i\.scdn\.co/image/ab67616d0000b273[\w]+)', r.text)
        if m:
            return m.group(1)
        # fallback: 640x640 معمولی
        m2 = re.search(
            r'(https://i\.scdn\.co/image/ab67616d00001e02[\w]+)', r.text)
        if m2:
            return m2.group(1)
    except Exception as e:
        log.warning("spotify big cover failed: %s", e)
    return ""


# ---------------------------------------------------------------- دستورات بات

WELCOME = """👋 سلام! من بات دانلودر هستم.

فقط لینک رو بفرست، خودم تشخیص می‌دم:

🟢 یوتیوب → ویدیو یا آهنگ
🎵 اسپاتیفای → آهنگ (MP3 با تگ کامل)
📱 تیک‌تاک → ویدیو بدون واترمارک

دستورات:
/videobox ۵۴۰ → کیفیت پایین‌تر برای یوتیوب
/song → آهنگ بعدی رو به صورت MP3 بفرست
/help → راهنما

⚡ حالت پیش‌فرض: یوتیوب و تیک‌تاک = ویدیو، اسپاتیفای = آهنگ"""

user_mode = {}  # chat_id -> "video" | "audio"


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def videobox_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """تغییر کیفیت پیش‌فرض ویدیو"""
    h = 720
    if ctx.args and ctx.args[0].isdigit():
        h = min(max(int(ctx.args[0]), 144), 1080)
    ctx.user_data["max_height"] = h
    await update.message.reply_text(f"✅ کیفیت ویدیو روی {h}p تنظیم شد")


async def song_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "audio"
    await update.message.reply_text(
        "🎵 حالت آهنگ فعال شد — لینک بعدی به صورت MP3 دانلود می‌شود\n"
        "(برای یوتیوب و اسپاتیفای)")


async def video_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "video"
    await update.message.reply_text(
        "🟢 حالت ویدیو فعال شد — لینک بعدی به صورت ویدیو دانلود می‌شود")


# ---------------------------------------------------------------- پردازش لینک

async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = update.effective_chat.id
    url = extract_url(msg.text or "")
    if not url:
        return
    platform = detect_platform(url)
    if not platform:
        await msg.reply_text(
            "🤔 این لینک رو نمی‌شناسم.\nاز یوتیوب، اسپاتیفای یا تیک‌تاک بفرست")
        return

    log.info("link from %s: %s", chat_id, url)
    mode = user_mode.pop(chat_id, None)  # یک‌بار مصرف: بعد از یک دانلود برمی‌گرده به پیش‌فرض
    want_audio = (mode == "audio")
    # اسپاتیفای همیشه آهنگ است
    if platform == "spotify":
        want_audio = True

    progress = await msg.reply_text("⏳ در حال دریافت اطلاعات...")
    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)

    try:
        if platform == "spotify":
            await progress.edit_text("🎵 در حال خواندن اطلاعات اسپاتیفای...")
            tracks = await asyncio.to_thread(spotify_tracks, url)
            if not tracks:
                raise RuntimeError(
                    "نتوانستم اطلاعات اسپاتیفای بخوانم — "
                    "ممکن است ترک در منطقه ما در دسترس نباشد. لینک دیگری امتحان کن.")
            ok_count = 0
            bot_blocked = 0
            await progress.edit_text(f"🎵 {len(tracks)} آهنگ پیدا شد")
            for i, meta in enumerate(tracks[:10], 1):  # حداکثر ۱۰ ترک
                query = f"{meta['artist']} {meta['title']}".strip()
                prefix = f"({i}/{len(tracks)}) " if len(tracks) > 1 else ""
                try:
                    await progress.edit_text(f"{prefix}🔎 جستجو: {query[:80]}")
                    yt = search_youtube_by_title(query, target_duration=meta.get("duration") or 0)
                    if not yt:
                        await progress.edit_text(f"{prefix}⚠️ «{meta['title'][:40]}» در یوتیوب پیدا نشد — رد شد")
                        continue
                    await progress.edit_text(f"{prefix}⬇️ دانلود و تبدیل به MP3...")
                    result = await asyncio.to_thread(
                        retry_download,
                        download_audio_mp3,
                        f"https://www.youtube.com/watch?v={yt['id']}",
                        title_hint=meta["title"],
                        artist=meta["artist"],
                        thumbnail=meta.get("cover") or "",
                    )
                    size = os.path.getsize(result["path"])
                    if size > MAX_TG_SIZE:
                        await progress.edit_text(f"{prefix}⚠️ «{meta['title'][:40]}» خیلی بزرگ است — رد شد")
                        cleanup(result["path"])
                        continue
                    await upload_result(ctx, chat_id, result, audio=True)
                    cleanup(result["path"])
                    ok_count += 1
                except Exception as te:
                    err = str(te)
                    if ("Sign in to confirm" in err or "needs to be reloaded" in err
                            or "unavailable" in err.lower()):
                        bot_blocked += 1
                    log.warning("track %s failed: %s", i, err[:120])
            if bot_blocked and not ok_count:
                await progress.edit_text(BOT_CHECK_MSG)
            elif bot_blocked:
                await progress.edit_text(
                    f"✅ {ok_count} آهنگ ارسال شد، {bot_blocked} تای دیگر به خاطر محدودیت یوتیوب رد شد.")
            else:
                await progress.delete()
            return
        else:
            kind = "آهنگ (MP3)" if want_audio else "ویدیو"
            await progress.edit_text(f"⬇️ در حال دانلود {kind}...")
            if want_audio:
                result = await asyncio.to_thread(retry_download, download_audio_mp3, url)
            else:
                result = await asyncio.to_thread(
                    retry_download,
                    download_video, url, platform,
                    ctx.user_data.get("max_height", 720),
                )

        size = os.path.getsize(result["path"])
        if size > MAX_TG_SIZE:
            await progress.edit_text(
                f"❌ فایل خیلی بزرگ است ({size // (1024*1024)}MB) — "
                "محدودیت تلگرام برای بات‌ها 49MB است.\n"
                "برای یوتیوب می‌توانی با /videobox 480 کیفیت را کم کنی.")
            cleanup(result["path"])
            return

        await progress.edit_text("📤 در حال آپلود در تلگرام...")
        await upload_result(ctx, chat_id, result, audio=want_audio or platform == "spotify")
        await progress.delete()
        cleanup(result["path"])

    except Exception as e:
        log.exception("download failed")
        err = str(e)
        if ("Sign in to confirm" in err or "needs to be reloaded" in err
                or "not a bot" in err.lower()):
            await progress.edit_text(BOT_CHECK_MSG)
        else:
            await progress.edit_text(f"❌ خطا: {err[:300]}")


async def upload_result(ctx, chat_id, result, audio: bool):
    path = result["path"]
    title = (result.get("title") or "file")[:60]
    if audio:
        with open(path, "rb") as f:
            await ctx.bot.send_audio(
                chat_id,
                f,
                title=title,
                performer=result.get("performer") or "",
                duration=result.get("duration") or None,
                thumbnail=result.get("cover") or None,
                read_timeout=300,
                write_timeout=300,
            )
    else:
        with open(path, "rb") as f:
            await ctx.bot.send_video(
                chat_id,
                f,
                caption=f"🎬 {title}",
                supports_streaming=True,
                duration=result.get("duration") or None,
                read_timeout=300,
                write_timeout=300,
            )


def cleanup(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------- شروع

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("متغیر BOT_TOKEN تنظیم نشده است")
    builder = create_bale_app()
    builder.token(token)
    builder.concurrent_updates(True)
    app = builder.build()
    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler("videobox", videobox_cmd))
    app.add_handler(CommandHandler("song", song_cmd))
    app.add_handler(CommandHandler("video", video_cmd))
    # هر پیامی که لینک داشته باشد
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"https?://"), handle_link))
    log.info("Bale bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
