import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

def _acquire_vault_path() -> Path:
    """Returns the base directory for sessions, ensuring it exists."""
    p = Path(settings.sessions_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _resolve_vault_file(session_id: str) -> Path:
    """Constructs the file path for a specific session."""
    return _acquire_vault_path() / f"{session_id}.json"

def _generate_utc_iso() -> str:
    """Helper to get standardized ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()

def extract_context_record(session_id: str) -> dict:
    """Loads a session from disk or initializes a new one if it doesn't exist."""
    path = _resolve_vault_file(session_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "session_id": session_id,
        "title": "New chat",
        "created_at": _generate_utc_iso(),
        "updated_at": _generate_utc_iso(),
        "messages": [],
    }

def flush_context_record(session_id: str, data: dict) -> None:
    """Persists session data dictionary to the file system as JSON."""
    data["updated_at"] = _generate_utc_iso()
    path = _resolve_vault_file(session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def register_interaction(session_id: str, role: str, content: str) -> None:
    """Appends a new user or assistant message to the session transcript."""
    data = extract_context_record(session_id)
    msg = {"role": role, "content": content, "ts": _generate_utc_iso()}
    data["messages"].append(msg)
    if role == "user" and data["title"] == "New chat":
        data["title"] = content[:60] + ("…" if len(content) > 60 else "")
    flush_context_record(session_id, data)

def query_all_active_threads() -> list[dict]:
    """Return all sessions sorted by updated_at desc (for sidebar)."""
    sessions_dir = _acquire_vault_path()
    sessions = []
    for f in sessions_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "session_id": data["session_id"],
                "title": data.get("title", "Chat"),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)

def purge_thread_data(session_id: str) -> None:
    """Deletes the JSON file associated with the given session ID."""
    path = _resolve_vault_file(session_id)
    if path.exists():
        os.remove(path)

def pull_message_timeline(session_id: str) -> list[dict]:
    """Gets only the list of messages for a session."""
    return extract_context_record(session_id).get("messages", [])
