import datetime as _dt
from typing import List, Optional
import requests

from .twitch_auth import twitch_headers

TWITCH_HELIX = "https://api.twitch.tv/helix"


def _get(url: str, params: dict | None = None) -> Optional[dict]:
    headers = twitch_headers()
    if not headers:
        return None
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"[twitch_stream_status] GET failed: {e}")
        return None


# ---------------- Users / Streams / Games ----------------


def get_users(logins: List[str]) -> list[dict]:
    if not logins:
        return []
    params = []
    for login in logins[:100]:
        params.append(("login", login))
    # Using list of tuples preserves duplicate keys; requests will encode correctly
    j = _get(f"{TWITCH_HELIX}/users", params=params)  # type: ignore
    return j.get("data", []) if j else []


def get_streams(logins: List[str]) -> list[dict]:
    if not logins:
        return []
    params = []
    for login in logins[:100]:
        params.append(("user_login", login))
    j = _get(f"{TWITCH_HELIX}/streams", params=params)  # type: ignore
    return j.get("data", []) if j else []


def get_games_by_ids(ids: List[str]) -> dict[str, dict]:
    if not ids:
        return {}
    params = []
    for gid in set(ids):
        params.append(("id", gid))
    j = _get(f"{TWITCH_HELIX}/games", params=params)  # type: ignore
    games = j.get("data", []) if j else []
    return {g.get("id"): g for g in games}


# ---------------- Search (for display name resolution) ----------------


def search_channels(query: str) -> list[dict]:
    if not query:
        return []
    j = _get(f"{TWITCH_HELIX}/search/channels", params={"query": query})
    return j.get("data", []) if j else []


def resolve_to_logins(identifiers: List[str]) -> dict[str, str]:
    """
    Accepts Twitch identifiers that may be *display names* or *logins* and
    resolves them to *logins*.

    Strategy:
    1) Try treating the identifier as a login (lowercased) with /users.
    2) If not found, use /search/channels?query=... and prefer exact display_name match;
       fall back to the first result.
    Returns mapping of original identifier -> resolved login.
    """
    out: dict[str, str] = {}
    if not identifiers:
        return out

    for raw in identifiers:
        candidate_login = raw.lower()

        # Try as login first
        u = get_users([candidate_login])
        if u:
            # Helix returns the canonical login
            out[raw] = (u[0].get("login") or candidate_login).lower()
            continue

        # Fallback: search by display name
        results = search_channels(raw)
        if not results:
            print(f"[resolver] Could not resolve '{raw}' via search.")
            continue

        exact = None
        lowered = raw.lower()
        for ch in results:
            # Prefer exact display_name (case-insensitive) if available
            if str(ch.get("display_name", "")).lower() == lowered:
                exact = ch
                break

        chosen = exact or results[0]
        login = chosen.get("broadcaster_login") or chosen.get("display_name") or lowered
        out[raw] = str(login).lower()

    # Deduplicate values while keeping the first mapping for each login
    seen = set()
    deduped: dict[str, str] = {}
    for k, v in out.items():
        if v in seen:
            continue
        seen.add(v)
        deduped[k] = v
    return deduped


# ---------------- Formatting helpers ----------------


def formatted_time(ts_iso: str, tzinfo) -> str:
    dt = _dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).astimezone(tzinfo)
    return dt.strftime("%-I:%M %p %Z")


def duration_hm(start: _dt.datetime, end: _dt.datetime) -> str:
    delta = end - start
    minutes = int(delta.total_seconds() // 60)
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


# ---------------- Build stream cards ----------------


def build_stream_cards(logins: List[str], tzinfo) -> dict[str, dict]:
    live = get_streams(logins)
    if not live:
        return {}

    game_ids = [s.get("game_id") for s in live if s.get("game_id")]
    games = get_games_by_ids([gid for gid in game_ids if gid])

    out: dict[str, dict] = {}
    for s in live:
        login = s.get("user_login")
        started_at = s.get("started_at")
        game_id = s.get("game_id")
        game_name = s.get("game_name") or "Just Chatting"
        title = s.get("title") or ""
        user_name = s.get("user_name") or login

        # Resolve box art
        box_art_url = None
        if game_id and game_id in games:
            tmpl = games[game_id].get("box_art_url") or ""
            if tmpl:
                box_art_url = tmpl.replace("{width}x{height}", "285x380")

        out[login.lower()] = {
            "login": login,
            "display_name": user_name,
            "title": title,
            "game_name": game_name,
            "game_id": game_id,
            "box_art_url": box_art_url,
            "started_at_iso": started_at,
            "started_at_local_str": formatted_time(started_at, tzinfo)
            if started_at
            else "Unknown",
            "started_at_dt": _dt.datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            if started_at
            else None,
        }
    return out
