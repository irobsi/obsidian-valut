import logging
import os
import yt_dlp

logger = logging.getLogger(__name__)


def download_track_audio(track_data: dict, mp3_path: str) -> bool:
    """
    Downloads a SoundCloud track to the given mp3_path.
    Returns True on success, False on failure.
    """
    url = track_data.get('url')
    if not url:
        logger.error("No URL in track_data")
        return False

    output_dir = os.path.dirname(mp3_path) or "."
    base = os.path.splitext(os.path.basename(mp3_path))[0]

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(output_dir, f"{base}.%(ext)s"),
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Check if the file exists (yt-dlp may use different naming)
        if os.path.exists(mp3_path):
            return True

        # Try glob fallback
        import glob
        pattern = os.path.join(output_dir, f"{base}*.mp3")
        files = glob.glob(pattern)
        if files:
            # Rename to expected path
            os.rename(files[0], mp3_path)
            return True

        logger.error("Download completed but output file not found")
        return False

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False
