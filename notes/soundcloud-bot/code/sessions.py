import time
from typing import Dict, Optional

class SessionManager:
    def __init__(self, ttl=1800):
        self._sessions: Dict[int, dict] = {}
        self._timestamps: Dict[int, float] = {}
        self.ttl = ttl  # Time-to-live in seconds

    def create_or_update(self, user_id: int, data: dict):
        """Stores or updates a session for a user."""
        self._sessions[user_id] = data
        self._timestamps[user_id] = time.time()
        # Trigger cleanup on each write to keep memory in check
        self._cleanup_expired()

    def get(self, user_id: int) -> Optional[dict]:
        """Retrieves a session if it exists and is not expired."""
        if user_id not in self._sessions:
            return None
        
        # Check if expired
        if time.time() - self._timestamps.get(user_id, 0) > self.ttl:
            self.delete(user_id)
            return None
        
        return self._sessions.get(user_id)

    def delete(self, user_id: int):
        """Explicitly deletes a user's session."""
        self._sessions.pop(user_id, None)
        self._timestamps.pop(user_id, None)

    def _cleanup_expired(self):
        """Internal cleanup that removes all expired sessions."""
        current_time = time.time()
        expired_users = [
            uid for uid, timestamp in self._timestamps.items()
            if current_time - timestamp > self.ttl
        ]
        for uid in expired_users:
            self.delete(uid)

    def get_all_active(self):
        """Returns a list of active user IDs (for debugging)."""
        self._cleanup_expired()
        return list(self._sessions.keys())
