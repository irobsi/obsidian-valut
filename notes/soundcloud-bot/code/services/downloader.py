import asyncio
import logging
import os
import re
from pathlib import Path
import yt_dlp
from soundcloud import extract_track_info

logger = logging.getLogger(__name__)

# Allowed characters for filenames
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

async def download_track_audio(track_url, output_dir="downloads"):
    """
    Downloads the audio from a SoundCloud URL asynchronously.
    Returns: (file_path, error_message)
    If successful: (Path_object, None)
    If failed: (None, "Error description")
    """
    # 1. Validate input
    if not track_url or not isinstance(track_url, str):
        return None, "Invalid URL provided."

    # 2. Ensure directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 3. Run the heavy yt-dlp work in a separate thread to avoid blocking the asyncio loop
    try:
        # Fetch info first (with validation)
        try:
            track_info = await asyncio.to_thread(extract_track_info, track_url)
        except ValueError as e:
            return None, str(e)

        # 4. Prepare filename
        safe_title = sanitize_filename(track_info['title'])
        safe_artist = sanitize_filename(track_info['uploader'])
        base_filename = f"{safe_artist} - {safe_title}"
        output_path = Path(output_dir) / f"{base_filename}.mp3"

        # 5. Set yt-dlp options with explicit outtmpl and error handling
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(Path(output_dir) / f"{base_filename}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,  # Overwrite if exists to avoid duplicates
        }

        # 6. Execute download
        def _sync_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download([track_url])
                if error_code != 0:
                    raise RuntimeError(f"yt-dlp exited with code {error_code}")
            
            # Check if the file actually exists
            expected_file = Path(output_dir) / f"{base_filename}.mp3"
            if not expected_file.exists():
                # Sometimes yt-dlp appends a number or uses a different format. Let's glob it.
                import glob
                pattern = str(Path(output_dir) / f"{base_filename}*.mp3")
                files = glob.glob(pattern)
                if files:
                    return Path(files[0])
                else:
                    raise FileNotFoundError("Download completed but output file not found.")
            return expected_file

        # Run the blocking download in a thread
        downloaded_file = await asyncio.to_thread(_sync_download)
        
        if not downloaded_file or not downloaded_file.exists():
            return None, "Download succeeded but file is missing."

        return downloaded_file, None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        return None, f"Download error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected download error: {e}")
        return None, f"An unexpected error occurred: {str(e)}"
