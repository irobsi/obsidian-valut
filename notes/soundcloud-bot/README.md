# SoundCloud Telegram Bot

ربات تلگرامی دانلود آهنگ از SoundCloud

## وابستگی‌ها
- Python 3.11+
- python-telegram-bot 22.8
- yt-dlp 2026.08.19+
- mutagen
- requests 2.34.2+
- ffmpeg (system)

## نصب
```bash
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot yt-dlp mutagen requests
```

## راه‌اندازی
1. فایل `config.py` رو با توکن ربات ویرایش کن
2. `python3 bot.py` اجرا کن

## ساختار فایل‌ها
```
bot.py          — اصلی، handlers و dispatcher
config.py       — توکن و تنظیمات
sessions.py     — مدیریت session کاربران
services/
  __init__.py
  soundcloud.py — API ساندکلاود
  downloader.py — دانلود و تبدیل فرمت
```

## نکات
- از `on.soundcloud.com` short links پشتیبانی میکنه
- فایل‌ها با ffmpeg به MP3 تبدیل میشن
- برای playlist فقط متادیتای اولین آهنگها برگردانده میشه → بقیه از /tracks/{id} گرفته میشه
- DRM protected tracks نادیده گرفته میشن
