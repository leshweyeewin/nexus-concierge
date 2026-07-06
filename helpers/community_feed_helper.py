"""
community_feed_helper.py
Live scraper for Singapore dev-community event sources: a public Telegram channel
(Google Developer Space), two community websites (GeeksHacking, GovTech STACK), and
a Meetup.com search — with a Gmail-scan cascade if Meetup is unreachable.

This mirrors the fetch_dev_event_feeds MCP tool in mcp_servers.py but is callable
directly from Streamlit, so the Events Hub tab can show the same live data the
DevRelopsAgent sees in chat, without spinning up the MCP subprocess.
"""

import re
import html
import urllib.request
from datetime import datetime, timezone

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_BASE_FEEDS = {
    "google developer space": {
        "source": "Google Developer Space Singapore",
        "icon": "📢",
        "agenda": "Build with AI Singapore: Gemini Deep Dive & Google Cloud Next Extended",
        "location": "📍 70 Pasir Panjang Rd, MBC II",
        "link": "https://t.me/s/googledevspacesg",
    },
    "geekshacking community": {
        "source": "GeeksHacking Community",
        "icon": "💻",
        "agenda": "HackOMania: Harnessing AI for Good Hackathon",
        "location": "📍 Lazada One or CapitaGreen",
        "link": "https://geekshacking.com/",
    },
    "stack community": {
        "source": "GovTech STACK Community",
        "icon": "🏛️",
        "agenda": "STACK Meetup: Why Data Reality Shapes AI Development",
        "location": "📍 GovTech Punggol Digital District",
        "link": "https://www.developer.tech.gov.sg/communities/events/stack-meetups/",
    },
    "meetup": {
        "source": "Meetup Singapore",
        "icon": "🗓️",
        "agenda": "Singapore Python User Group Meetup: GenAI with ADK",
        "location": "📍 Singapore Town Event",
        "link": "https://www.meetup.com/find/?source=EVENTS&keywords=developer&location=sg--Singapore",
    },
}


def _fetch_telegram_channel(channel: str, feed_info: dict, num_posts: int = 2) -> dict:
    """Scrape a public Telegram channel's web preview (t.me/s/<channel>). Channels
    whose owner has disabled the web preview return a page with no post markup —
    that's a legitimate channel setting, not an error, so we mark it 'offline' and
    link straight to the channel rather than show nothing."""
    url = f"https://t.me/s/{channel}"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            page_html = response.read().decode("utf-8")
        posts_with_ids = re.findall(
            r'<div class="tgme_widget_message[^"]*"\s+data-post="([^"]+)"[^>]*>.*?'
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            page_html, re.DOTALL,
        )
        # Each message's <time datetime="..."> footer appears after its own data-post
        # attribute and before the next message's — non-greedy DOTALL matching on
        # data-post -> next <time> reliably pairs each post with its own timestamp.
        post_dates = dict(re.findall(
            r'data-post="([^"]+)"[^>]*>.*?<time datetime="([^"]+)"',
            page_html, re.DOTALL,
        ))
        if posts_with_ids:
            clean_posts = []
            for post_id, p in posts_with_ids:
                p_clean = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
                clean_posts.append({
                    "text": p_clean,
                    "link": f"https://t.me/{post_id}",
                    "posted_at": post_dates.get(post_id),
                })
            # Sort by actual post timestamp (ISO 8601 strings sort chronologically),
            # latest first — posts with no parsed timestamp sort last instead of
            # breaking the comparison.
            clean_posts.sort(key=lambda post: post["posted_at"] or "", reverse=True)
            feed_info["posts"] = clean_posts[:num_posts]
            feed_info["live_status"] = "live"
        else:
            feed_info["live_status"] = "offline"
            feed_info["error"] = "Channel has no public web preview (owner disabled it, or no posts)."
    except Exception as e:
        feed_info["live_status"] = "offline"
        feed_info["error"] = str(e)
    feed_info["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    return feed_info


def _fetch_telegram(feed_info: dict) -> dict:
    return _fetch_telegram_channel("googledevspacesg", feed_info)


TRADING_TELEGRAM_CHANNELS = {
    # Note: Telegram's public web preview (t.me/s/<name>) only exists for broadcast
    # channels, never for groups — group content is never readable without an
    # authenticated login, regardless of scraping approach. "Tiger Brokers Options",
    # "The Safe Investor", "Tiger Options Camp", and "TB CashBoost" were confirmed to
    # be groups (removed here) rather than channels, so they always showed OFFLINE.
    "stocktradingandanalysis": {"source": "Stock Trading & Analysis", "channel": "stocktradingandanalysis"},
    "poemsta": {"source": "POEMS TA", "channel": "POEMSTA"},
}


def fetch_trading_feeds(sources: list | None = None) -> list:
    """Live-scrape the public trading Telegram channels the user follows. `sources`
    restricts to a subset of TRADING_TELEGRAM_CHANNELS keys; None fetches all.
    Each returned dict always has 'live_status' ('live' or 'offline') plus a
    'link' to the channel so the UI can send users there when preview is disabled."""
    targets = sources or list(TRADING_TELEGRAM_CHANNELS.keys())
    results = []
    for key in targets:
        cfg = TRADING_TELEGRAM_CHANNELS.get(key)
        if not cfg:
            continue
        feed_info = {
            "source": cfg["source"],
            "icon": "\U0001F4C8",
            "link": f"https://t.me/{cfg['channel']}",
        }
        results.append(_fetch_telegram_channel(cfg["channel"], feed_info))
    return results


def _fetch_headings(feed_info: dict, url: str, tags: str) -> dict:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8")
        headings = re.findall(rf"<h[{tags}][^>]*>(.*?)</h[{tags}]>", html, re.DOTALL)
        clean = [re.sub(r"<[^>]+>", "", h).strip() for h in headings if len(h.strip()) > 2]
        if clean:
            feed_info["headings"]    = clean[:5]
            feed_info["live_status"] = "live"
        else:
            feed_info["live_status"] = "offline"
    except Exception as e:
        feed_info["live_status"] = "offline"
        feed_info["error"] = str(e)
    return feed_info


def _fetch_meetup(feed_info: dict) -> dict:
    url = _BASE_FEEDS["meetup"]["link"]
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8")
        titles = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, re.DOTALL)
        clean = [re.sub(r"<[^>]+>", "", t).strip() for t in titles if len(t.strip()) > 3]
        clean = [t for t in clean if not t.startswith("Groups") and not t.startswith("Explore")][:3]
        if not clean:
            raise Exception("No meetup cards found on search layout.")
        feed_info["headings"]    = clean
        feed_info["live_status"] = "live"
    except Exception as e:
        feed_info["live_status"] = "offline"
        feed_info["error"] = str(e)
    return feed_info


def fetch_community_feeds(sources: list | None = None) -> list:
    """
    Live-scrape Singapore dev-community sources. `sources` restricts to a subset of
    {"google developer space", "geekshacking community", "stack community", "meetup"};
    None fetches all four. Each returned dict always has a usable "live_status"
    ("live" or "offline") and a static fallback agenda/location so the UI never goes blank.
    """
    targets = sources or list(_BASE_FEEDS.keys())
    results = []
    for key in targets:
        if key not in _BASE_FEEDS:
            continue
        feed_info = _BASE_FEEDS[key].copy()

        if key == "google developer space":
            feed_info = _fetch_telegram(feed_info)
        elif key == "geekshacking community":
            feed_info = _fetch_headings(feed_info, "https://geekshacking.com/", "1234")
        elif key == "stack community":
            feed_info = _fetch_headings(
                feed_info, "https://www.developer.tech.gov.sg/communities/events/stack-meetups/", "23")
        elif key == "meetup":
            feed_info = _fetch_meetup(feed_info)

        results.append(feed_info)
    return results
