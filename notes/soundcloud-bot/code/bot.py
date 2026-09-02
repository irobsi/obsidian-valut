#!/usr/bin/env python3
import asyncio
import logging
import os
import tempfile

from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, APIC, error as ID3Error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from services import soundcloud as sc
from config import (
    BOT_TOKEN,
    ALLOWED_USER_IDS,
    PAGE_SIZE,
    SEARCH_PAGE_SIZE,
)
from services.downloader import download_track_audio
from sessions import user_sessions, touch_session, cleanup_old_sessions

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS


async def reject_unauthorized(update: Update) -> None:
    message = update.effective_message
    if message:
        await message.reply_text("⛔ دسترسی ندارید.")


def fmt_duration(ms: int | None) -> str:
    if not ms:
        return "—"
    seconds = int(ms) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def add_cover_art_to_mp3(mp3_path: str, track_info: dict) -> str | None:
    artwork_url = (
        track_info.get("artwork_url")
        or track_info.get("user", {}).get("avatar_url")
    )
    if not artwork_url:
        return None

    artwork_url = artwork_url.replace("large.jpg", "t500x500.jpg")
    thumb_path = mp3_path + ".jpg"

    try:
        import requests

        response = requests.get(
            artwork_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()

        with open(thumb_path, "wb") as f:
            f.write(response.content)

        try:
            audio = ID3(mp3_path)
        except ID3Error:
            audio = ID3()

        title = track_info.get("title", "Unknown")
        artist = track_info.get("user", {}).get("username", "SoundCloud")

        audio.delall("TIT2")
        audio.delall("TPE1")
        audio.delall("TALB")
        audio.delall("TRCK")
        audio.delall("APIC")

        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=artist))
        audio.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=response.content,
            )
        )
        audio.save(mp3_path)
        return thumb_path

    except Exception:
        logger.exception("Failed to add cover art")
        return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await reject_unauthorized(update)
        return

    await update.message.reply_text(
        "👋 سلام! به ربات دانلود موزیک ساندکلاود خوش آمدید.\n\n"
        "🎵 قابلیت‌ها:\n"
        "• ارسال لینک ترک یا پلی‌لیست ساندکلاود\n"
        "• ارسال نام آهنگ برای جستجوی مستقیم\n"
        "• انتخاب چندتایی آهنگ از پلی‌لیست\n\n"
        "آهنگ یا لینک خود را بفرستید:"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        await reject_unauthorized(update)
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    cleanup_old_sessions()
    touch_session(uid)

    try:
        if sc.is_sc_url(text):
            if "sets/" in text or "playlist" in text:
                await handle_playlist(update, context, text)
            else:
                await handle_single_track(update, context, text)
        else:
            await handle_search(update, context, text, page=0)
    except Exception:
        logger.exception("Unhandled message error for user %s", uid)
        await update.message.reply_text(
            "❌ عملیات انجام نشد. جزئیات خطا در log ثبت شده است."
        )


async def handle_single_track(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text("⏳ در حال دریافت اطلاعات ترک...")

    data = await asyncio.to_thread(sc.resolve_soundcloud_url, url)
    if not data or "id" not in data:
        await msg.edit_text("❌ ترک پیدا نشد یا SoundCloud پاسخ مناسبی نداد.")
        return

    title = data.get("title", "Unknown")
    await msg.edit_text(f"⬇️ در حال دانلود: {title}")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            mp3_path = os.path.join(tmp_dir, f"{data['id']}.mp3")
            ok = await asyncio.to_thread(download_track_audio, data, mp3_path)

            if not ok:
                await msg.edit_text(
                    "❌ این ترک قابل دانلود نیست یا SoundCloud/yt-dlp آن را محدود کرده است."
                )
                return

            thumb_path = await asyncio.to_thread(
                add_cover_art_to_mp3, mp3_path, data
            )

            with open(mp3_path, "rb") as audio_file:
                thumb_file = (
                    open(thumb_path, "rb")
                    if thumb_path and os.path.exists(thumb_path)
                    else None
                )
                try:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=title,
                        performer=data.get("user", {}).get("username", "SoundCloud"),
                        duration=data.get("duration", 0) // 1000,
                        caption=f"🎵 {title}\n🔗 {url}",
                        thumbnail=thumb_file,
                    )
                finally:
                    if thumb_file:
                        thumb_file.close()

            await msg.delete()

    except Exception:
        logger.exception("Single track download error")
        await msg.edit_text(
            "❌ دانلود یا ارسال فایل انجام نشد. جزئیات خطا در log ثبت شده است."
        )


async def handle_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text("⏳ در حال بارگذاری پلی‌لیست...")

    title, tracks = await asyncio.to_thread(sc.get_playlist_tracks, url)
    if not tracks:
        await msg.edit_text("❌ پلی‌لیست خالی است یا یافت نشد.")
        return

    uid = update.effective_user.id
    user_sessions[uid] = {
        "tracks": tracks,
        "selected": set(),
        "page": 0,
        "playlist_title": title,
        "msg_id": msg.message_id,
        "kind": "playlist",
    }
    touch_session(uid)
    await send_playlist_page(msg, uid)


def build_playlist_keyboard(session: dict) -> InlineKeyboardMarkup:
    tracks = session["tracks"]
    selected = session["selected"]
    page = session["page"]

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(tracks))
    total_pages = max(1, (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE)

    keyboard = []
    for idx in range(start, end):
        track = tracks[idx]
        title = track.get("title", "Track")
        duration = fmt_duration(track.get("duration"))
        icon = "✅" if idx in selected else "⬜️"
        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {idx + 1}. {title[:30]} ({duration})",
                callback_data=f"toggle:{idx}",
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data="page:prev"))
    nav.append(InlineKeyboardButton(
        f"📄 {page + 1}/{total_pages}", callback_data="noop"
    ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data="page:next"))
    keyboard.append(nav)

    all_selected = len(selected) == len(tracks)
    keyboard.append([
        InlineKeyboardButton(
            "🔲 لغو انتخاب همه" if all_selected else "☑️ انتخاب همه",
            callback_data="toggle:all",
        ),
        InlineKeyboardButton("🔄 بازنشانی", callback_data="reset"),
    ])
    keyboard.append([
        InlineKeyboardButton(
            f"⬇️ دانلود انتخاب‌شده‌ها ({len(selected)})",
            callback_data="download",
        )
    ])
    keyboard.append([
        InlineKeyboardButton("❌ انصراف", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


async def send_playlist_page(msg, uid: int):
    session = user_sessions.get(uid)
    if not session:
        return

    text = (
        f"📂 **{session['playlist_title']}**\n"
        f"تعداد کل: {len(session['tracks'])} ترک\n"
        f"انتخاب‌شده: {len(session['selected'])} ترک\n\n"
        "لطفاً آهنگ‌های مورد نظر را انتخاب کنید:"
    )
    try:
        await msg.edit_text(
            text,
            reply_markup=build_playlist_keyboard(session),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to refresh playlist page")


def build_search_keyboard(session: dict) -> InlineKeyboardMarkup:
    tracks = session["tracks"]
    selected = session["selected"]

    keyboard = []
    for idx, track in enumerate(tracks):
        title = track.get("title", "Track")
        artist = track.get("user", {}).get("username", "SC")
        duration = fmt_duration(track.get("duration"))
        icon = "✅" if idx in selected else "⬜️"

        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {idx + 1}. {artist} - {title[:25]} ({duration})",
                callback_data=f"toggle:{idx}",
            )
        ])

    page = session["page"]
    has_more = session.get("has_more", False)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data="search:prev"))
    nav.append(InlineKeyboardButton(
        f"📄 {page + 1}", callback_data="noop"
    ))
    if has_more:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data="search:next"))
    keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton(
            f"⬇️ دانلود انتخاب‌شده‌ها ({len(selected)})",
            callback_data="download",
        )
    ])
    keyboard.append([
        InlineKeyboardButton("☑️ انتخاب همه", callback_data="toggle:all"),
        InlineKeyboardButton("❌ انصراف", callback_data="cancel"),
    ])

    return InlineKeyboardMarkup(keyboard)


async def handle_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    page: int = 0,
):
    uid = update.effective_user.id
    msg = await update.message.reply_text(
        f"🔍 در حال جستجو برای: {query}..."
    )

    tracks, has_more = await asyncio.to_thread(
        sc.search_tracks,
        query,
        page * SEARCH_PAGE_SIZE,
        SEARCH_PAGE_SIZE,
    )

    if not tracks:
        await msg.edit_text("❌ نتیجه‌ای پیدا نشد.")
        return

    user_sessions[uid] = {
        "tracks": tracks,
        "selected": set(),
        "page": page,
        "query": query,
        "playlist_title": f"نتیجه جستجو: {query}",
        "msg_id": msg.message_id,
        "kind": "search",
        "has_more": has_more,
    }
    touch_session(uid)
    await send_search_page(msg, uid)


async def send_search_page(msg, uid: int):
    session = user_sessions.get(uid)
    if not session:
        return

    text = (
        f"🔎 **{session['playlist_title']}**\n"
        f"انتخاب‌شده: {len(session['selected'])}\n\n"
        "برای دانلود، آهنگ‌ها را انتخاب کنید:"
    )
    try:
        await msg.edit_text(
            text,
            reply_markup=build_search_keyboard(session),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to refresh search page")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if not is_authorized(uid):
        await q.edit_message_text("⛔ دسترسی ندارید.")
        return

    touch_session(uid)
    session = user_sessions.get(uid)

    if q.data == "noop":
        return

    if q.data == "cancel":
        user_sessions.pop(uid, None)
        await q.edit_message_text("❌ عملیات لغو شد.")
        return

    if not session:
        await q.edit_message_text(
            "❌ نشست منقضی شده است. لطفاً دوباره لینک یا جستجو بفرستید."
        )
        return

    data = q.data
    tracks = session["tracks"]
    selected = session["selected"]

    if data.startswith("toggle:"):
        value = data.split(":", 1)[1]

        if value == "all":
            if len(selected) == len(tracks):
                selected.clear()
            else:
                selected.clear()
                selected.update(range(len(tracks)))

        else:
            idx = int(value)
            if 0 <= idx < len(tracks):
                if idx in selected:
                    selected.remove(idx)
                else:
                    selected.add(idx)

    elif data == "reset":
        selected.clear()
        session["page"] = 0

    elif data == "page:prev":
        session["page"] = max(0, session["page"] - 1)

    elif data == "page:next":
        total_pages = max(1, (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE)
        session["page"] = min(total_pages - 1, session["page"] + 1)

    elif data == "search:prev":
        if session["page"] > 0:
            await handle_search(
                update,
                context,
                session["query"],
                session["page"] - 1,
            )
        return

    elif data == "search:next":
        if session.get("has_more"):
            await handle_search(
                update,
                context,
                session["query"],
                session["page"] + 1,
            )
        return

    elif data == "download":
        if not selected:
            await q.answer("هیچ آهنگی انتخاب نشده!", show_alert=True)
            return

        await download_selected(q, session, uid, sorted(selected))
        return

    if session.get("kind") == "search":
        await send_search_page(q.message, uid)
    else:
        await send_playlist_page(q.message, uid)


async def download_selected(q, session: dict, uid: int, indices: list[int]):
    total = len(indices)
    sent = 0
    failed = []

    await q.edit_message_text(f"⏳ شروع دانلود {total} آهنگ...")

    for position, idx in enumerate(indices, start=1):
        track = session["tracks"][idx]
        title = track.get("title", f"track_{track.get('id')}")

        try:
            await q.message.reply_text(
                f"⬇️ {position}/{total}: {title}"
            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                mp3_path = os.path.join(
                    tmp_dir,
                    f"{track.get('id', position)}.mp3",
                )

                ok = await asyncio.to_thread(
                    download_track_audio,
                    track,
                    mp3_path,
                )

                if not ok:
                    failed.append(title)
                    continue

                track_info = await asyncio.to_thread(
                    sc.get_track_info,
                    track.get("id"),
                )
                if not track_info:
                    track_info = track

                thumb_path = await asyncio.to_thread(
                    add_cover_art_to_mp3,
                    mp3_path,
                    track_info,
                )

                with open(mp3_path, "rb") as audio_file:
                    thumb_file = (
                        open(thumb_path, "rb")
                        if thumb_path and os.path.exists(thumb_path)
                        else None
                    )
                    try:
                        await q.message.reply_audio(
                            audio=audio_file,
                            title=title,
                            performer=track_info.get("user", {}).get(
                                "username", "SoundCloud"
                            ),
                            duration=track_info.get("duration", 0) // 1000,
                            caption=f"🎵 {title}",
                            thumbnail=thumb_file,
                        )
                        sent += 1
                    finally:
                        if thumb_file:
                            thumb_file.close()

        except Exception:
            logger.exception(
                "Download failed for user=%s track=%s",
                uid,
                track.get("id"),
            )
            failed.append(title)

    summary = f"✅ {sent}/{total} آهنگ ارسال شد"
    if failed:
        summary += f"\n❌ ناموفق: {len(failed)}"

    await q.message.reply_text(summary)
    user_sessions.pop(uid, None)


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("SoundCloud bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()