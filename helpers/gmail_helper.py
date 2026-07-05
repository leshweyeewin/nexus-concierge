"""
gmail_helper.py
Searches the user's Gmail inbox for meetup / dev-event invitations.

Shares Google OAuth credentials with google_calendar_helper.py (same token.json,
same combined SCOPES) so there's one "Connect Google" flow for both Calendar and
Gmail rather than two separate sign-ins. Never blocks on interactive auth — falls
back to representative simulated emails if not connected or on any API error.
"""

from .google_calendar_helper import _load_silent_credentials  # noqa: F401 (re-exported for app.py)

DEFAULT_QUERY = "meetup OR meetup.com OR rsvp OR eventbrite"

_SIMULATED_EMAILS = [
    {
        "sender": "noreply@meetup.com",
        "subject": "Event Confirmed: Go-Singapore Developer Meetup July 2026",
        "snippet": "Your ticket is confirmed. Agenda covers Go 1.28 concurrent memory models.",
        "date": "Wed, 1 Jul 2026 10:00:00 +0800",
        "link": "",
    },
    {
        "sender": "passg@founders.sg",
        "subject": "Invitation to SG AI Founders Pitch Night & Networking",
        "snippet": "Join us for networking, investor matchings, and panel debates on cloud orchestration.",
        "date": "Sun, 28 Jun 2026 09:00:00 +0800",
        "link": "",
    },
    {
        "sender": "info@geekshacking.com",
        "subject": "HackOMania Hackathon registration open",
        "snippet": "Register now for HackOMania 2026. Bring your Python, Open Source, and GenAI skills!",
        "date": "Thu, 25 Jun 2026 14:30:00 +0800",
        "link": "",
    },
]


def fetch_meetup_emails(query: str = DEFAULT_QUERY, max_results: int = 10) -> dict:
    """
    Search Gmail for meetup/event invitations without ever blocking on interactive auth.

    Result shape: {"emails": [...], "is_simulated": bool, "error": str | None}
    """
    creds = _load_silent_credentials()
    if creds is None:
        return {"emails": _SIMULATED_EMAILS[:max_results], "is_simulated": True, "error": None}

    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])

        emails = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = detail.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender  = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
            date    = next((h["value"] for h in headers if h["name"] == "Date"), "")
            emails.append(
                {
                    "sender": sender,
                    "subject": subject,
                    "snippet": detail.get("snippet", ""),
                    "date": date,
                    "link": f"https://mail.google.com/mail/u/0/#all/{msg['id']}",
                }
            )
        return {"emails": emails, "is_simulated": False, "error": None}
    except Exception as e:
        return {"emails": _SIMULATED_EMAILS[:max_results], "is_simulated": True, "error": str(e)}
