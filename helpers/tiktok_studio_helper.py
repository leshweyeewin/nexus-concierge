"""
tiktok_studio_helper.py
Two link-in, content-out tools for the TikTok tab:
  - generate_product_promo(url): paste a product link -> promo idea, script, shooting suggestions.
  - analyze_tiktok_video(url):   paste a TikTok video link -> what's working / not working critique.

Both do a best-effort public-page scrape for context (title, description, hashtags, and — for
TikTok video pages — embedded stats when present in server-rendered HTML), then hand that
context to Gemini for the actual writing/critique. TikTok has no public analytics API for
individual creators, and scraping can be blocked or return partial data at any time — every
function degrades gracefully and labels what it could and couldn't fetch, rather than failing.
"""

import os
import re
import json
import ipaddress
import socket
import urllib.request
from urllib.parse import urlparse

MODEL_NAME = "gemini-2.5-flash"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def _get_client():
    from google.genai import Client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No GEMINI_API_KEY or GOOGLE_API_KEY set — cannot call the model.")
    return Client(api_key=api_key)


def _assert_public_http_url(url: str) -> None:
    """Reject anything but http(s) URLs resolving to a public address, so a pasted
    link can't be used to make this server-side fetch hit internal/loopback
    services (SSRF) — these fields take arbitrary user-typed URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only http/https URLs are allowed.")
    try:
        addrs = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host: {e}")
    for family, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("URL resolves to a non-public address.")


def _fetch_html(url: str, timeout: int = 8) -> str:
    _assert_public_http_url(url)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _extract_meta(html: str) -> dict:
    """Best-effort <title>/og:title/og:description scrape — works on most product pages."""
    def _find(pattern):
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    title = (
        _find(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']')
        or _find(r"<title[^>]*>(.*?)</title>")
    )
    description = (
        _find(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']')
        or _find(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']')
    )
    image = _find(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']')
    price = _find(r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)["\']')
    return {"title": title, "description": description, "image": image, "price": price}


def _extract_tiktok_stats(html: str) -> dict:
    """
    TikTok server-renders a JSON blob (SIGI_STATE or the newer __UNIVERSAL_DATA_FOR_REHYDRATION__)
    into the page for the initial paint. Pull stats out of whichever is present. TikTok may serve
    a stripped-down page to non-browser clients, so this can legitimately come back empty.
    """
    for script_id in ("__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE"):
        m = re.search(
            rf'<script id="{script_id}"[^>]*>(.*?)</script>', html, re.DOTALL,
        )
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue

        # Walk the (deeply nested, version-dependent) structure looking for a stats-shaped dict.
        found = {}

        def _walk(node):
            if found:
                return
            if isinstance(node, dict):
                if {"diggCount", "playCount"} & set(node.keys()):
                    found.update(node)
                    return
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(data)
        if found:
            return {
                "views": found.get("playCount"),
                "likes": found.get("diggCount"),
                "comments": found.get("commentCount"),
                "shares": found.get("shareCount"),
                "saves": found.get("collectCount"),
            }
    return {}


def generate_product_promo(product_url: str, extra_context: str = "") -> dict:
    """
    Scrape a product page (best-effort) and ask Gemini for a promo idea, script, and
    shooting suggestions in the CreativeAffiliateAgent's voice.

    Result shape: {"text": str, "scraped": dict, "error": str | None}
    """
    scraped = {}
    scrape_error = None
    try:
        html = _fetch_html(product_url)
        scraped = _extract_meta(html)
    except Exception as e:
        scrape_error = str(e)

    context_lines = [f"Product URL: {product_url}"]
    if scraped.get("title"):
        context_lines.append(f"Page title: {scraped['title']}")
    if scraped.get("description"):
        context_lines.append(f"Page description: {scraped['description']}")
    if scraped.get("price"):
        context_lines.append(f"Price: {scraped['price']}")
    if scrape_error:
        context_lines.append(f"(Could not fetch page contents automatically: {scrape_error}. "
                              f"Work from the URL and any extra context given.)")
    if extra_context:
        context_lines.append(f"Extra context from the creator: {extra_context}")

    prompt = (
        "You are the CreativeAffiliateAgent, a TikTok Shop affiliate copywriter. A creator has "
        "given you a product link to promote. Using the context below, write:\n"
        "1. **Promo Idea** — one-sentence creative angle.\n"
        "2. **Script** — Hook (first 2 seconds), Body (3-5 short beats), CTA.\n"
        "3. **Shooting Suggestions** — shots, props, setting, pacing.\n"
        "4. **Hashtags** — 5-8 relevant tags.\n\n"
        "Keep it punchy and native to TikTok Shop style, not corporate ad copy.\n\n"
        + "\n".join(context_lines)
    )

    client = _get_client()
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return {"text": response.text, "scraped": scraped, "error": scrape_error}


def analyze_tiktok_video(video_url: str, extra_context: str = "") -> dict:
    """
    Scrape a TikTok video page (best-effort) for description/hashtags/stats and ask Gemini
    to critique what's working and what's not, with concrete suggestions.

    Result shape: {"text": str, "scraped": dict, "stats_found": bool, "error": str | None}
    """
    scraped = {}
    stats = {}
    scrape_error = None
    try:
        html = _fetch_html(video_url)
        scraped = _extract_meta(html)
        stats = _extract_tiktok_stats(html)
    except Exception as e:
        scrape_error = str(e)

    context_lines = [f"Video URL: {video_url}"]
    if scraped.get("description"):
        context_lines.append(f"Caption/description: {scraped['description']}")
    if stats:
        stat_bits = [f"{k}: {v}" for k, v in stats.items() if v is not None]
        if stat_bits:
            context_lines.append("Engagement stats found: " + ", ".join(stat_bits))
    if not stats:
        context_lines.append(
            "(No engagement stats could be scraped — TikTok often blocks non-browser requests "
            "or serves a stripped page. Base the critique on the caption/hook/hashtags only, "
            "and say so explicitly rather than inventing numbers.)"
        )
    if scrape_error:
        context_lines.append(f"(Page fetch failed: {scrape_error}. Work from the URL and any "
                              f"extra context given, and say the fetch failed.)")
    if extra_context:
        context_lines.append(f"Extra context from the creator (e.g. manually reported stats): {extra_context}")

    prompt = (
        "You are the CreativeAffiliateAgent, a TikTok performance analyst for affiliate "
        "creators. Given the context below, write a short critique with:\n"
        "1. **What's Working** — 2-3 concrete points (hook, pacing, caption, hashtags, or stats if available).\n"
        "2. **What's Not Working** — 2-3 concrete, honest points.\n"
        "3. **Next Video Suggestions** — 2-3 specific, actionable changes.\n\n"
        "If engagement stats weren't available, be explicit that this critique is based on "
        "caption/hook/hashtags only, not real performance data. Don't invent numbers.\n\n"
        + "\n".join(context_lines)
    )

    client = _get_client()
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return {"text": response.text, "scraped": scraped, "stats_found": bool(stats), "error": scrape_error}
