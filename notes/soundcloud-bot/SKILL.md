---
name: soundcloud-bot
description: Run/maintain @inure_soundcloudbot (token 8912423296:***). Telegram bot that searches & downloads SoundCloud tracks/playlists as MP3. Use when user asks to start, fix, or modify this bot.
---

# SoundCloud Downloader Bot

Telegram bot for downloading SoundCloud tracks and playlists as MP3. Bot: **@inure_soundcloudbot**. Owner: inure (Persian/Farsi).

## Quick Start

```bash
cd /data/workspace/soundcloud-bot
source venv/bin/activate
python3 bot.py
```

Or run in background:
```bash
cd /data/workspace/soundcloud-bot && source venv/bin/activate && python3 bot.py
```

## Files (do NOT push to GitHub — contains bot token)

- `bot.py` — main entry (596 lines), handlers for /start, text messages, callback queries
- `config.py` — `BOT_TOKEN`, `ALLOWED_USER_IDS`, page sizes
- `sessions.py` — in-memory session store (TTL 30 min)
- `services/__init__.py` — empty
- `services/soundcloud.py` — URL detection, playlist/search resolution via yt-dlp
- `services/downloader.py` — yt-dlp + ffmpeg postprocessor → MP3

## Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot mutagen yt-dlp requests
apt install ffmpeg
```

## Features

- Direct track link → single MP3
- Playlist/set link → multi-select UI (checkboxes, select all, page nav)
- Free-text search (`scsearch{N}`) → multi-select UI, paginated
- Cover art embedded as ID3 APIC frame
- Title/artist/performer sent to Telegram audio metadata
- `/start` welcome

## Allowed Users (in config.py)

`[7747086163, 6605229065, 1994789266]` — all others get "⛔ دسترسی ندارید."

## Key Bugs Already Solved (do NOT re-introduce)

1. **outtmpl with .mp3 extension → produces `.mp3.mp3` files.** When ffmpeg postprocessor is set to mp3, the file becomes `{path}.mp3`, not `{path}`. Fix:
   ```python
   'outtmpl': mp3_path.rsplit('.', 1)[0] if '.' in mp3_path else mp3_path,
   ```
   Then existence check on the original `mp3_path` works.

2. **Use `webpage_url`, not `url` for download.** yt-dlp's `entry['url']` returns a signed streaming URL that 403s. Always prefer `entry.get('webpage_url') or entry.get('url')` in `_entry_to_track`.

3. **`ignoreerrors: True` on search/extract_info.** Some SoundCloud tracks are DRM-protected and raise an exception that would otherwise break the entire search result. Without it, the bot reports "❌ نتیجه‌ای پیدا نشد" for valid queries just because one entry is DRM-blocked.

4. **Short URL resolution.** `on.soundcloud.com/...` and similar redirects must be resolved first via `requests.head(allow_redirects=True)` before passing to yt-dlp.

5. **Only one bot instance.** If two `python3 bot.py` processes run, telegram raises `Conflict: terminated by other getUpdates request`. Always `pkill -f "python3 bot.py"` before restart.

## Debugging

- Log: `/data/workspace/soundcloud-bot/bot.log`
- Direct test of search: `cd /data/workspace/soundcloud-bot && source venv/bin/activate && python3 -c "from services import soundcloud as sc; print(sc.search_tracks('query', 0, 5))"`
- Direct test of download: same with `from services.downloader import download_track_audio`
- `bot_1_.py` was the original user-provided file before this codebase existed; current `bot.py` replaces it.

## Modifying the Bot

User prefers minimal/silent execution. After any code change:
```bash
pkill -f "python3 bot.py"; sleep 2
cd /data/workspace/soundcloud-bot && source venv/bin/activate && python3 bot.py
```
Report back only when the bot is verified running and a test download succeeded.
