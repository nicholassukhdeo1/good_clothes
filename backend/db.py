# db.py — tiny Supabase layer for persisting user preferences.
# We hit Supabase's PostgREST API over plain HTTP (no extra dependency, same style as
# the image fetch in alternatives.py). If SUPABASE_URL/KEY aren't set, every call is a
# safe no-op so the app keeps working — persistence just lights up once keys are added.
#
# The service_role key lives ONLY here (backend/.env). Never ship it in the extension.

import json
import urllib.request
import urllib.parse
from config import SUPABASE_URL, SUPABASE_KEY

TABLE = "preferences"


def enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def get_pref(user_id: str):
    """Return the saved pref string for this user, or None."""
    if not enabled() or not user_id:
        return None
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?user_id=eq.{urllib.parse.quote(user_id)}&select=pref"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            rows = json.loads(r.read().decode("utf-8"))
        return rows[0]["pref"] if rows else None
    except Exception:
        return None


def set_pref(user_id: str, pref: str) -> bool:
    """Upsert (user_id, pref). Returns True on success."""
    if not enabled() or not user_id:
        return False
    # Prefer: merge-duplicates makes this an upsert on the user_id primary key.
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    body = json.dumps([{"user_id": user_id, "pref": pref}]).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers=_headers({"Prefer": "resolution=merge-duplicates"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            return True
    except Exception:
        return False
