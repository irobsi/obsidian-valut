import logging
import yt_dlp

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def extract_track_info(url):
    """
    Extracts track information from a SoundCloud URL.
    Raises ValueError if the URL is invalid or no downloadable URL is found.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Invalid URL provided.")
    
    # Basic URL validation for SoundCloud
    if not (url.startswith("https://soundcloud.com/") or url.startswith("https://on.soundcloud.com/")):
        raise ValueError("URL does not appear to be a valid SoundCloud link.")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,  # Kept to bypass DRM, but we check the result explicitly
        'extract_flat': False,
        'format': 'bestaudio/best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise ValueError("Could not extract track info (URL might be private or deleted).")

            # Critical fix: Ensure we have a direct downloadable URL
            track_url = info.get('url')
            if not track_url:
                # Fallback: sometimes it's under 'webpage_url' or we need to request a format
                # yt-dlp usually provides 'url' for direct stream. If missing, raise error.
                logger.error(f"No direct download URL found for: {url}. Info keys: {info.keys()}")
                raise ValueError("Track is not downloadable (possibly requires authentication or DRM).")

            # Build a clean result dict
            return {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown Artist'),
                'duration': info.get('duration', 0),
                'url': track_url,  # The actual audio stream URL
                'thumbnail': info.get('thumbnail'),
            }

    except Exception as e:
        logger.error(f"yt-dlp extraction failed for {url}: {str(e)}")
        # Re-raise a clean error for the bot to handle
        raise ValueError(f"Failed to fetch track: {str(e)}")
