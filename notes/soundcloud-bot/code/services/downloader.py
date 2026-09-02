import os
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def download_track_audio(track_info: dict, mp3_path: str) -> bool:
    """Download audio from SoundCloud using yt-dlp.
    Returns True on success, False otherwise.
    """
    try:
        from yt_dlp import YoutubeDL

        # yt-dlp can download from SoundCloud URLs
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': mp3_path.rsplit('.', 1)[0] if '.' in mp3_path else mp3_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'postprocessor_args': [
                '-loglevel', 'quiet',
            ],
            'quiet': True,
            'no_warnings': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([track_info['url'] if 'url' in track_info else None])
        return os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0
    except Exception as e:
        logger.exception("Failed to download track: %s", e)
        return False