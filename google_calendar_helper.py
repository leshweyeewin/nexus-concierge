"""
google_calendar_helper.py
Reusable helper to authenticate with Google Calendar and fetch upcoming events.
Called directly from app.py so the Calendar tab works without starting the MCP subprocess.
"""

import os
import datetime

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


def _get_credentials():
    """Return valid Google OAuth2 credentials, refreshing or re-authorising as needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "Google credentials.json not found. Download an OAuth 2.0 Client ID "
                    "from Google Cloud Console (APIs & Services -> Credentials) and save it "
                    "as 'credentials.json' in the project root. Then run this tool once to "
                    "authorise via browser."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def fetch_calendar_events(max_results: int = 15) -> list:
    """
    Return a list of upcoming Google Calendar events as structured dicts.

    Each dict contains:
      - summary (str): event title
      - start (str): ISO-8601 datetime or date string
      - end (str): ISO-8601 datetime or date string
      - link (str): HTML link to the event
      - location (str|None): event location if set
      - description (str|None): event description if set
      - is_all_day (bool): True when the event spans a full day
    """
    from googleapiclient.discovery import build

    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
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
            }
        )
    return events


def credentials_available() -> bool:
    """Return True if credentials.json or token.json exist."""
    return os.path.exists(CREDENTIALS_PATH) or os.path.exists(TOKEN_PATH)
