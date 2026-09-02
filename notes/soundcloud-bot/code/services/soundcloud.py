import re
import requests
from typing import Optional, Tuple, List, Dict, Any

SC_URL_RE = re.compile(r'https?://(?:www\.|on\.)?soundcloud\.com/[^\s]+', re.IGNORECASE)

def is_sc_url(text: str) -> bool:
    return bool(SC_URL_RE.search(text))


def _resolve_short_url(url: str) -> str:
    """Resolve on.soundcloud.com / sc links."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return r.url
    except Exception:
        return url


def _extract_info(url: str) -> Optional[Dict[Any, Any]]:
    try:
        from yt_dlp import YoutubeDL
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ignoreerrors': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def resolve_soundcloud_url(url: str) -> Optional[Dict[Any, Any]]:
    url = _resolve_short_url(url)
    info = _extract_info(url)
    if not info:
        return None
    if info.get('_type') == 'playlist' and info.get('entries'):
        entry = info['entries'][0] if info['entries'] else None
        if entry:
            entry['url'] = info.get('webpage_url', url)
            return entry
    return info


def _entry_to_track(entry: Any) -> Optional[Dict[Any, Any]]:
    if not entry:
        return None
    return {
        'id': entry.get('id'),
        'title': entry.get('title'),
        'duration': entry.get('duration', 0) * 1000,
        'url': entry.get('webpage_url') or entry.get('url'),
        'user': {
            'username': entry.get('uploader', 'SoundCloud')
        },
        'artwork_url': entry.get('thumbnail'),
    }


def get_playlist_tracks(url: str) -> Tuple[str, List[Dict[Any, Any]]]:
    url = _resolve_short_url(url)
    info = _extract_info(url)
    if not info:
        return "", []
    if info.get('_type') != 'playlist':
        return info.get('title', 'Unknown'), [_entry_to_track(info)]
    title = info.get('title', 'Unknown Playlist')
    tracks = []
    for entry in info.get('entries', []):
        t = _entry_to_track(entry)
        if t:
            tracks.append(t)
    return title, tracks


def search_tracks(query: str, offset: int, limit: int) -> Tuple[List[Dict[Any, Any]], bool]:
    search_url = f"scsearch{limit}:{query}"
    info = _extract_info(search_url)
    if not info:
        return [], False
    tracks = []
    for entry in info.get('entries', []):
        t = _entry_to_track(entry)
        if t:
            tracks.append(t)
    has_more = len(tracks) == limit
    return tracks, has_more


def get_track_info(track_id: Any) -> Optional[Dict[Any, Any]]:
    try:
        from yt_dlp import YoutubeDL
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ignoreerrors': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{track_id}", download=False)
            if info and info.get('entries'):
                return _entry_to_track(info['entries'][0])
    except Exception:
        pass
    return None