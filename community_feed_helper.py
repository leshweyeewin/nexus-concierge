"""
community_feed_helper.py
Live scraper for Singapore dev-community event sources: a public Telegram channel
(Google Developer Space), two community websites (GeeksHacking, GovTech STACK), and
a Meetup.com search — with a Gmail-scan cascade if Meetup is unreachable.

This mirrors the fetch_dev_event_feeds MCP tool in mcp_servers.py but is callable
directly from Streamlit, so the Events Hub tab can show the same live data the
DevRelopsAgent sees in chat, without spinning up the MCP subprocess.
"""

import os
import re
import json
import urllib.request

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


def _fetch_telegram(feed_info: dict) -> dict:
    url = "https://t.me/s/googledevspacesg"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8")
        posts_with_ids = re.findall(
            r'<div class="tgme_widget_message[^"]*"\s+data-post="([^"]+)"[^>]*>.*?'
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL,
        )
        if posts_with_ids:
            clean_posts = []
            for post_id, p in posts_with_ids[-2:]:
                p_clean = re.sub(r"<[^>]+>", "", p)
                p_clean = (p_clean.replace("&amp;", "&").replace("&#33;", "!")
                           .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').strip())
                clean_posts.append({"text": p_clean, "link": f"https://t.me/{post_id}"})
            feed_info["posts"] = clean_posts
            feed_info["live_status"] = "live"
        else:
            feed_info["live_status"] = "offline"
    except Exception as e:
        feed_info["live_status"] = "offline"
        feed_info["error"] = str(e)
    return feed_info


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
