"""
twitter_feed_helper.py
Unofficial, no-login scraper for public X/Twitter profile timelines via the
cdn.syndication.twimg.com embed endpoint (the same backend X's own website-embed
widgets use). This is unauthenticated and unofficial: X can rate-limit, block,
or change the response shape without notice.

If a fetch fails, we mark that account "offline" and link out to its profile —
we never fabricate tweet text, since a wrong/expired quote is worse than none.
"""

import json
import time
import urllib.request
import urllib.error

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

TRADING_X_HANDLES = [
    "BarbArmstrongCS",
    "JamesBoydCS",
    "CameronMayCS",
    "ConnieHillCS",
    "MikeFairbournCS",
    "BenWatsonCS",
    "BrentMoorsCS",
    "RachelDashCS",
]


def _extract_tweets(payload: dict) -> list:
    """Defensively pull tweets out of the syndication timeline response, whose
    shape isn't publicly documented and may shift over time."""
    entries = (payload.get("timeline") or {}).get("entries") or []
    tweets = []
    for entry in entries:
        tweet = ((entry.get("content") or {}).get("tweet")) or entry.get("tweet")
        if not tweet:
            continue
        text = tweet.get("full_text") or tweet.get("text")
        tweet_id = tweet.get("id_str") or tweet.get("id")
        screen_name = ((tweet.get("user") or {}).get("screen_name"))
        if not text or not tweet_id:
            continue
        link = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name else None
        tweets.append({"text": text.strip(), "link": link})
    return tweets


def _fetch_handle(handle: str, retries: int = 2) -> dict:
    handle = handle.lstrip("@")
    feed_info = {
        "source": f"@{handle}",
        "icon": "\U0001F426",
        "link": f"https://x.com/{handle}",
    }
    url = f"https://cdn.syndication.twimg.com/timeline/profile?screen_name={handle}&lang=en"

    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as response:
                raw = response.read().decode("utf-8")
            if not raw.strip():
                raise ValueError("empty response from syndication endpoint")
            payload = json.loads(raw)
            tweets = _extract_tweets(payload)
            if tweets:
                feed_info["posts"] = tweets[:3]
                feed_info["live_status"] = "live"
                return feed_info
            last_error = "no tweets found in response"
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2)
                continue
        except Exception as e:
            last_error = str(e)
        break

    feed_info["live_status"] = "offline"
    feed_info["error"] = last_error
    return feed_info


def fetch_twitter_feeds(handles: list | None = None) -> list:
    """Fetch recent posts for each handle. Each returned dict always has a
    usable 'live_status' ('live' or 'offline') so the UI never goes blank;
    on 'offline' there is no 'posts' key and callers should link to the profile
    instead of showing stale/fabricated content."""
    targets = handles or TRADING_X_HANDLES
    results = []
    for i, handle in enumerate(targets):
        if i > 0:
            time.sleep(1)  # be polite to the unofficial endpoint, avoid tripping rate limits
        results.append(_fetch_handle(handle))
    return results
