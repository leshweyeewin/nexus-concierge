"""
google_calendar_helper.py
Reusable helper to authenticate with Google (Calendar + Gmail) and fetch upcoming events.
Called directly from app.py so the Calendar tab works without starting the MCP subprocess.
gmail_helper.py reuses the credential/OAuth functions here so both features share one
token.json and one "Connect" flow instead of two separate Google sign-ins.

Design note: fetching events NEVER triggers an interactive browser OAuth popup —
that would block the Streamlit request thread and looks like a hang/crash. Instead:
  - fetch_calendar_events() uses only an existing token.json (refreshing silently
    if possible) and falls back to simulated demo events on any auth/API failure.
  - run_oauth_flow() is the explicit, user-triggered action (e.g. a "Connect"
    button) that opens the browser consent screen and saves token.json.
"""

import os
import datetime

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

# Google Calendar's built-in event color palette IDs, used as tags:
#   Basil (deep green)   -> Dev events
#   Sage  (pistachio/grey-green) -> Trading events
DEV_COLOR_ID      = "10"  # Basil
TRADING_COLOR_ID  = "2"   # Sage (Pistachio)

_SIMULATED_EVENTS = [
    {
        "summary": "SG AI Founders Pitch Night & Networking",
        "start": "2026-07-04T19:00:00+08:00",
        "end": "2026-07-04T21:00:00+08:00",
        "link": "https://calendar.google.com/calendar/event?eid=mock1",
        "location": "Punggol Digital District",
        "description": "Simulated demo event — connect your real Google Calendar for live data.",
        "is_all_day": False,
        "color_id": DEV_COLOR_ID,
    },
    {
        "summary": "Build with AI Singapore: Gemini Deep Dive",
        "start": "2026-07-06T18:30:00+08:00",
        "end": "2026-07-06T20:30:00+08:00",
        "link": "https://calendar.google.com/calendar/event?eid=mock2",
        "location": "Google Singapore",
        "description": "Simulated demo event — connect your real Google Calendar for live data.",
        "is_all_day": False,
        "color_id": DEV_COLOR_ID,
    },
    {
        "summary": "Go-Singapore Developer Meetup",
        "start": "2026-07-10T19:00:00+08:00",
        "end": "2026-07-10T21:00:00+08:00",
        "link": "https://calendar.google.com/calendar/event?eid=mock3",
        "location": None,
        "description": "Simulated demo event — connect your real Google Calendar for live data.",
        "is_all_day": False,
        "color_id": DEV_COLOR_ID,
    },
    {
        "summary": "US CPI Print & Rate Decision Watch",
        "start": "2026-07-08T20:30:00+08:00",
        "end": "2026-07-08T21:30:00+08:00",
        "link": "https://calendar.google.com/calendar/event?eid=mock4",
        "location": None,
        "description": "Simulated demo event — connect your real Google Calendar for live data.",
        "is_all_day": False,
        "color_id": TRADING_COLOR_ID,
    },
    {
        "summary": "Quarterly Options Expiry (OpEx) Review",
        "start": "2026-07-11T09:30:00+08:00",
        "end": "2026-07-11T10:30:00+08:00",
        "link": "https://calendar.google.com/calendar/event?eid=mock5",
        "location": None,
        "description": "Simulated demo event — connect your real Google Calendar for live data.",
        "is_all_day": False,
        "color_id": TRADING_COLOR_ID,
    },
]


def _load_silent_credentials():
    """Return valid credentials from token.json only, refreshing if needed. Never opens a browser."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not os.path.exists(TOKEN_PATH):
        return None

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except Exception:
        return None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
            return creds
        except Exception:
            return None

    return None


def is_headless_cloud_host() -> bool:
    """True when running on a remote host with no local browser to complete the
    installed-app OAuth loopback redirect (e.g. Render, Heroku, Cloud Run). Render
    sets RENDER=true for every service; the others are common equivalents.
    Used to disable the 'Connect' button instead of hanging the request forever
    waiting on a callback nothing can ever deliver."""
    return any(os.environ.get(v) for v in ("RENDER", "DYNO", "K_SERVICE", "WEBSITE_INSTANCE_ID"))


def run_oauth_flow():
    """Explicitly run the interactive browser OAuth consent flow and persist token.json.

    Only call this in direct response to a user action (e.g. a button click) —
    never automatically during a page render.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if is_headless_cloud_host():
        raise RuntimeError(
            "Interactive OAuth isn't available on this deployment (no local browser can "
            "complete the sign-in redirect). Run this app locally to connect a real Google "
            "account, or provide a pre-authorized token.json via a Secret File."
        )

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            "Google credentials.json not found. Download an OAuth 2.0 Client ID "
            "from Google Cloud Console (APIs & Services -> Credentials) and save it "
            "as 'credentials.json' in the project root."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    return creds


def is_connected() -> bool:
    """True if a valid (or silently refreshable) Google Calendar token is available."""
    return _load_silent_credentials() is not None


def fetch_calendar_events(max_results: int = 15, colors=None) -> dict:
    """
    Return upcoming Google Calendar events without ever blocking on interactive auth.

    colors: optional iterable of Google Calendar colorIds to restrict results to
    (e.g. {DEV_COLOR_ID, TRADING_COLOR_ID}). None/empty means no color filter — all events.

    Result shape: {"events": [...], "is_simulated": bool, "error": str | None}
    Falls back to representative simulated events if not connected or on any API error.
    """
    color_set = set(colors) if colors else None

    creds = _load_silent_credentials()
    if creds is None:
        sim = _SIMULATED_EVENTS
        if color_set:
            sim = [e for e in sim if e.get("color_id") in color_set]
        return {"events": sim[:max_results], "is_simulated": True, "error": None}

    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now = datetime.datetime.utcnow().isoformat() + "Z"

        # Fetch a larger raw batch when filtering by color, since colorId can't be
        # filtered server-side in events().list() — we filter client-side below.
        fetch_limit = max(max_results * 4, 50) if color_set else max_results

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=fetch_limit,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for item in result.get("items", []):
            color_id = item.get("colorId")
            if color_set and color_id not in color_set:
                continue
            start_raw = item["start"].get("dateTime") or item["start"].get("date")
            end_raw = item["end"].get("dateTime") or item["end"].get("date")
            is_all_day = "date" in item["start"] and "dateTime" not in item["start"]
            events.append(
                {
                    "summary": item.get("summary", "Untitled Event"),
                    "start": start_raw,
                    "end": end_raw,
                    "link": item.get("htmlLink", ""),
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "is_all_day": is_all_day,
                    "color_id": color_id,
                }
            )
            if len(events) >= max_results:
                break
        return {"events": events, "is_simulated": False, "error": None}
    except Exception as e:
        sim = _SIMULATED_EVENTS
        if color_set:
            sim = [e for e in sim if e.get("color_id") in color_set]
        return {"events": sim[:max_results], "is_simulated": True, "error": str(e)}


def credentials_available() -> bool:
    """Return True if credentials.json exists, so the Connect button can be shown."""
    return os.path.exists(CREDENTIALS_PATH)


def oauth_connect_supported() -> bool:
    """Return True only if a real 'Connect' click could actually complete: credentials.json
    is present AND we're not on a headless cloud host with no local browser to finish the
    OAuth redirect."""
    return credentials_available() and not is_headless_cloud_host()
