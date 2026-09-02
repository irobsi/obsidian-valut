import time

user_sessions: dict[int, dict] = {}
SESSION_TTL = 1800  # 30 minutes


def touch_session(uid: int) -> None:
    session = user_sessions.get(uid)
    if session:
        session["last_active"] = time.time()


def cleanup_old_sessions() -> None:
    now = time.time()
    expired = [
        uid
        for uid, s in user_sessions.items()
        if now - s.get("last_active", now) > SESSION_TTL
    ]
    for uid in expired:
        user_sessions.pop(uid, None)
