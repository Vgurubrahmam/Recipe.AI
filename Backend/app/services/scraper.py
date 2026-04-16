"""
app/services/scraper.py
─────────────────────────────────────────────────────────────
Async web scraper for recipe blog pages.

Strategy cascade (tried in order, first success wins):

  1. httpx + recipe-scrapers (JSON-LD / microdata)
     Fetches the page with realistic browser headers via httpx,
     then runs `recipe-scrapers` to read structured Schema.org/Recipe
     JSON-LD or microdata. Falls back to BeautifulSoup text.

  2. cloudscraper (Cloudflare JS-challenge bypass)
     Emulates a real browser TLS fingerprint to pass Cloudflare's
     JS challenge. Runs recipe-scrapers on the fetched HTML first.

  3. Bing Cache
     Fetches the Bing-cached version of the page via cc.bingj.com.
     Bypasses paywalls and most bot-detection because Bing's cache
     is plain public HTML. Google Cache was deprecated in Feb 2024.

  4. Wayback Machine (archive.org)
     Fetches the latest archived snapshot from the Internet Archive.
     Works even when Bing has no cache for the URL.

  5. Playwright headless browser
     Full headless Chromium. Executes JavaScript, waits for the DOM
     to settle, and masks webdriver fingerprints.
     Requires: pip install playwright && playwright install chromium

All strategies share the same URL validation and text cleaning
utilities. The first strategy that returns ≥ 150 characters of
cleaned text is used; if all five fail, a ScrapingError is raised.
"""

import asyncio
import hashlib
import logging
import random
import time
from urllib.parse import quote as _url_quote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.middleware.error_handler import ScrapingError
from app.utils.helpers import clean_text

logger = logging.getLogger(__name__)

# ── Realistic browser User-Agents (rotated per request) ─────
_USER_AGENTS = [
    # Chrome 124 / Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # Chrome 123 / macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Firefox 125 / Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    # Edge 124 / Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    ),
    # Safari 17 / macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
]

# ── HTML tags that never contain recipe content ──────────────
_NOISE_TAGS = [
    "script", "style", "noscript", "header", "footer",
    "nav", "aside", "form", "button", "iframe", "svg",
    "meta", "link", "head", "advertisement", "ads",
]

# ── Domains known to return 402/403 to ALL automated scrapers ──
# For these we skip httpx + cloudscraper and go straight to Google Cache.
_KNOWN_BLOCKED_DOMAINS = {
    "allrecipes.com",
    "www.allrecipes.com",
}

def _is_known_blocked(url: str) -> bool:
    """Return True if the URL's hostname is in the known-blocked list."""
    try:
        return urlparse(url).hostname in _KNOWN_BLOCKED_DOMAINS
    except Exception:
        return False


# ── Minimum text length to consider a scrape successful ─────
_MIN_TEXT_LENGTH = 150
_BLOCK_PAGE_MARKERS = [
    "just a moment",
    "cf-browser-verification",   # Cloudflare challenge page div
    "challenge-running",         # Cloudflare JS challenge body class
    "cf_chl_opt",                # Cloudflare challenge JS variable
    "ray id",                    # Cloudflare 403/503 error page footer
    "captcha",
    "access denied",
    "attention required",
    "verify you are human",
    "robot check",
    "bot detection",
]


# ════════════════════════════════════════════════════════════
# Shared helpers
# ════════════════════════════════════════════════════════════

def _build_headers(url: str) -> dict:
    """
    Build a realistic browser-like header set for the given URL.

    Selects a random User-Agent and populates all headers a real
    browser sends, making the request harder to fingerprint as a bot.
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": origin,
    }


def _validate_url(url: str) -> None:
    """
    Validate URL structure (scheme + host).

    Raises:
        ScrapingError: For structurally invalid URLs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ScrapingError(
                f"Invalid URL scheme '{parsed.scheme}'. Only http/https are supported."
            )
        if not parsed.netloc:
            raise ScrapingError(f"URL '{url}' has no hostname.")
    except Exception as exc:
        if isinstance(exc, ScrapingError):
            raise
        raise ScrapingError(f"Malformed URL: {url}") from exc


def _extract_text_from_html(html: str) -> str:
    """
    Parse raw HTML and extract the main recipe text content via BeautifulSoup.

    Strategy (priority order):
    1. <article>  — most recipe blogs wrap content here
    2. <main>     — semantic fallback
    3. <div> with "recipe" in class/id
    4. <div> with "content" / "post" / "entry" in class/id
    5. <body>     — last resort

    Returns:
        Cleaned, truncated text. Empty string if nothing extractable found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove all noise tags
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Priority content selectors
    content = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=lambda c: c and "recipe" in c.lower())
        or soup.find("div", id=lambda i: i and "recipe" in i.lower())
        or soup.find("div", class_=lambda c: c and any(
            k in c.lower() for k in ("content", "post", "entry", "article")
        ))
        or soup.find("body")
    )

    if not content:
        return ""

    raw_text = content.get_text(separator="\n")
    return clean_text(raw_text, max_length=settings.scraper_max_text_length)


def _detect_block_signals(status_code: int, html: str, headers: dict[str, str]) -> list[str]:
    """
    Detect anti-bot / WAF response indicators.
    """
    signals: list[str] = []
    lower_html = html.lower()

    # 402 = Payment Required is used by AllRecipes and others to block bots
    if status_code in (402, 403, 429, 503):
        signals.append(f"http_{status_code}")

    for marker in _BLOCK_PAGE_MARKERS:
        if marker in lower_html:
            signals.append(f"marker:{marker}")

    return signals


def _html_preview(html: str, max_len: int) -> str:
    """
    Build a compact single-line HTML preview for log comparison.
    """
    return " ".join(html[:max_len].split())


def _log_fetch_diagnostics(
    *,
    strategy: str,
    url: str,
    attempt: int,
    status_code: int,
    final_url: str,
    headers: dict[str, str],
    html: str,
) -> None:
    """
    Log status/header/body signatures for local vs cloud comparison.
    """
    content_type = headers.get("content-type", "")
    server = headers.get("server", "")
    via = headers.get("via", "")
    html_hash = hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()[:12]
    block_signals = _detect_block_signals(status_code, html, headers)

    logger.info(
        "[scrape-diagnostic] strategy=%s attempt=%d status=%d final_url=%s len=%d hash=%s "
        "content_type=%s server=%s via=%s block_signals=%s",
        strategy,
        attempt,
        status_code,
        final_url,
        len(html),
        html_hash,
        content_type,
        server,
        via,
        ",".join(block_signals) if block_signals else "none",
    )

    if settings.scraper_enable_response_debug:
        logger.debug(
            "[scrape-diagnostic-html] strategy=%s attempt=%d preview=%s",
            strategy,
            attempt,
            _html_preview(html, settings.scraper_debug_snippet_length),
        )


# ════════════════════════════════════════════════════════════
# Strategy 1 — recipe-scrapers (JSON-LD / microdata)
# ════════════════════════════════════════════════════════════

def _try_recipe_scrapers(url: str, html: str) -> str:
    """
    Attempt structured data extraction via the `recipe-scrapers` library.

    Reads Schema.org/Recipe JSON-LD or microdata embedded in the page.
    This is far more reliable than raw text parsing and works on many
    Cloudflare-protected sites because the structured data is server-rendered.

    Returns:
        Formatted recipe text block, or empty string on any failure.
    """
    try:

        scraper = scrape_html(html, org_url=url)

        parts: list[str] = []

        def _safe(fn):
            try:
                return fn()
            except Exception:
                return None

        title = _safe(scraper.title)
        if title:
            parts.append(f"Title: {title}")

        prep_time = _safe(scraper.prep_time)
        if prep_time:
            parts.append(f"Prep Time: {prep_time} minutes")

        cook_time = _safe(scraper.cook_time)
        if cook_time:
            parts.append(f"Cook Time: {cook_time} minutes")

        total_time = _safe(scraper.total_time)
        if total_time:
            parts.append(f"Total Time: {total_time} minutes")


        servings = _safe(scraper.yields)
        if servings:
            parts.append(f"Servings: {servings}")

        ingredients = _safe(scraper.ingredients)
        if ingredients:
            parts.append("Ingredients:")
            parts.extend(f"  - {ing}" for ing in ingredients)

        instructions = _safe(scraper.instructions)
        if instructions:
            parts.append("Instructions:")
            parts.append(instructions)

        description = _safe(scraper.description)
        if description:
            parts.append(f"Description: {description}")

        cuisine = _safe(scraper.cuisine)
        if cuisine:
            parts.append(f"Cuisine: {cuisine}")

        result = "\n".join(parts)
        logger.debug(
            "recipe-scrapers extracted %d characters from %s", len(result), url
        )
        return result

    except Exception as exc:
        logger.debug("recipe-scrapers failed for %s: %s", url, exc)
        return ""


# ════════════════════════════════════════════════════════════
# Strategy 2 — cloudscraper (Cloudflare bypass)
# ════════════════════════════════════════════════════════════

async def _try_cloudscraper(url: str) -> tuple[str, str]:
    """
    Fetch the URL using `cloudscraper` to bypass Cloudflare JS challenges.

    cloudscraper emulates a real browser TLS fingerprint and solves the
    Cloudflare challenge in Python, making it invisible to the JS gate.
    Returns both the raw HTML and the BeautifulSoup-extracted text so the
    caller can also run recipe-scrapers on the structured data.

    Runs the synchronous cloudscraper call in a thread pool to avoid
    blocking the event loop.

    Returns:
        (html, extracted_text) tuple. Both empty strings on any failure.
    """
    def _fetch_sync() -> tuple[str, str]:
        try:
            import cloudscraper  # type: ignore

            for attempt in range(1, settings.scraper_max_retries + 1):
                cs = cloudscraper.create_scraper(
                    browser={
                        "browser": "chrome",
                        "platform": "windows",
                        "mobile": False,
                    }
                )
                resp = cs.get(
                    url,
                    timeout=settings.scraper_request_timeout,
                    headers=_build_headers(url),
                )
                html = resp.text or ""
                headers = {k.lower(): v for k, v in resp.headers.items()}
                _log_fetch_diagnostics(
                    strategy="cloudscraper",
                    url=url,
                    attempt=attempt,
                    status_code=resp.status_code,
                    final_url=str(resp.url),
                    headers=headers,
                    html=html,
                )

                signals = _detect_block_signals(resp.status_code, html, headers)
                if resp.status_code == 200 and not signals:
                    return html, _extract_text_from_html(html)

                if attempt < settings.scraper_max_retries:
                    sleep_seconds = settings.scraper_retry_backoff_base * (2 ** (attempt - 1))
                    time.sleep(sleep_seconds)

            logger.debug("cloudscraper exhausted retries for %s", url)
            return "", ""
        except Exception as exc:
            logger.debug("cloudscraper failed for %s: %s", url, exc)
            return "", ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync)


# ════════════════════════════════════════════════════════════
# Strategy 3 — httpx + BeautifulSoup (plain HTML)
# ════════════════════════════════════════════════════════════

async def _try_httpx(url: str) -> tuple[str, str]:
    """
    Fetch URL via httpx with realistic browser headers.

    Returns:
        (html_text, extracted_text) tuple.
        Both are empty strings on failure.

    Raises:
        ScrapingError: On network-level errors that should surface to the user
                       (timeout, too many redirects, unexpected status codes).
    """
    last_status: int | None = None
    last_signals: list[str] = []
    for attempt in range(1, settings.scraper_max_retries + 1):
        headers = _build_headers(url)
        try:
            try:
                async with httpx.AsyncClient(
                    headers=headers,
                    timeout=settings.scraper_request_timeout,
                    follow_redirects=True,
                    cookies={},
                    http2=True,
                ) as client:
                    response = await client.get(url)
            except ImportError:
                logger.warning(
                    "http2 extras not installed; falling back to HTTP/1.1 for %s",
                    url,
                )
                async with httpx.AsyncClient(
                    headers=headers,
                    timeout=settings.scraper_request_timeout,
                    follow_redirects=True,
                    cookies={},
                    http2=False,
                ) as client:
                    response = await client.get(url)
        except httpx.TimeoutException:
            if attempt < settings.scraper_max_retries:
                await asyncio.sleep(settings.scraper_retry_backoff_base * (2 ** (attempt - 1)))
                continue
            raise ScrapingError(
                f"Request timed out after {settings.scraper_request_timeout}s. "
                "The site may be slow or blocking automated access."
            )
        except httpx.TooManyRedirects:
            raise ScrapingError(f"Too many redirects for URL: {url}")
        except httpx.RequestError as exc:
            if attempt < settings.scraper_max_retries:
                await asyncio.sleep(settings.scraper_retry_backoff_base * (2 ** (attempt - 1)))
                continue
            raise ScrapingError(f"Network error while fetching '{url}': {exc}") from exc

        html = response.text or ""
        response_headers = {k.lower(): v for k, v in response.headers.items()}
        last_status = response.status_code
        _log_fetch_diagnostics(
            strategy="httpx",
            url=url,
            attempt=attempt,
            status_code=response.status_code,
            final_url=str(response.url),
            headers=response_headers,
            html=html,
        )
        last_signals = _detect_block_signals(response.status_code, html, response_headers)

        # HTTP error handling
        if response.status_code == 404:
            raise ScrapingError(f"Page not found (HTTP 404): {url}")

        # 402/403/429/503 or block signals — fall through immediately (no retries on hard blocks)
        if response.status_code in (402, 403, 429, 503) or last_signals:
            # 402 is a deliberate bot-block — retrying wastes time, skip immediately
            if response.status_code == 402:
                logger.warning(
                    "httpx got 402 for %s — bot-blocked, skipping retries.", url
                )
                return "", ""

            if attempt < settings.scraper_max_retries:
                retry_after = response_headers.get("retry-after")
                try:
                    delay = float(retry_after) if retry_after else (
                        settings.scraper_retry_backoff_base * (2 ** (attempt - 1))
                    )
                except ValueError:
                    delay = settings.scraper_retry_backoff_base * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
                continue

            logger.warning(
                "httpx blocked for %s (status=%s, signals=%s). Falling through to next strategy.",
                url,
                response.status_code,
                ",".join(last_signals) if last_signals else "none",
            )
            return "", ""

        if response.status_code >= 500:
            if attempt < settings.scraper_max_retries:
                await asyncio.sleep(settings.scraper_retry_backoff_base * (2 ** (attempt - 1)))
                continue
            raise ScrapingError(
                f"Target site returned HTTP {response.status_code} after retries."
            )

        if response.status_code not in (200, 201):
            # Treat unexpected non-success codes as soft failures so the next
            # strategy can attempt the URL.
            logger.warning(
                "httpx got unexpected status %s for %s — falling through.",
                response.status_code, url,
            )
            return "", ""

        content_type = response_headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ScrapingError(
                f"Expected HTML but received '{content_type}'. "
                "This URL may point to a PDF, image, or API endpoint."
            )

        text = _extract_text_from_html(html)
        return html, text

    raise ScrapingError(
        "Could not fetch page content after retries. "
        f"Last status={last_status}, signals={','.join(last_signals) if last_signals else 'none'}."
    )


# ════════════════════════════════════════════════════════════
# Strategy 3 — Bing Cache
# ════════════════════════════════════════════════════════════

async def _try_bing_cache(url: str) -> tuple[str, str]:
    """
    Fetch the Bing-cached version of a URL via cc.bingj.com.

    Google Cache was deprecated in February 2024 and now returns a
    short "no longer available" page. Bing's cache is still live and
    serves plain archived HTML — bypassing paywalls, 402/403 blocks,
    and JS rendering for most recipe sites.

    Returns:
        (html, extracted_text) tuple. Both empty strings on any failure.
    """
    encoded = _url_quote(url, safe="")
    cache_url = f"https://cc.bingj.com/cache.aspx?q={encoded}&url={encoded}&mkt=en-US"
    logger.debug("Bing Cache fetching: %s", cache_url)
    try:
        headers = _build_headers(cache_url)
        async with httpx.AsyncClient(
            headers=headers,
            timeout=settings.scraper_request_timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(cache_url)

        if response.status_code != 200:
            logger.debug(
                "Bing Cache returned HTTP %d for %s", response.status_code, url
            )
            return "", ""

        html = response.text or ""

        # Bing wraps the cached page in a thin toolbar <div> at top.
        from bs4 import BeautifulSoup as _BS
        soup = _BS(html, "lxml")
        for tag in soup.find_all(id="bingcache-toolbar"):
            tag.decompose()
        clean_html = str(soup)

        # Prefer structured JSON-LD from the cached HTML
        structured = _try_recipe_scrapers(url, clean_html)
        if len(structured) >= _MIN_TEXT_LENGTH:
            logger.debug("Bing Cache: recipe-scrapers succeeded (%d chars)", len(structured))
            return clean_html, structured

        # Prepend <h1> as "Title:" so LLM always has a title anchor
        title_tag = soup.find("h1")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        bs4_text = _extract_text_from_html(clean_html)
        if page_title and not bs4_text.startswith("Title:"):
            bs4_text = f"Title: {page_title}\n{bs4_text}"

        return clean_html, bs4_text

    except Exception as exc:
        logger.debug("Bing Cache failed for %s: %s", url, exc)
        return "", ""


# ════════════════════════════════════════════════════════════
# Strategy 4 — Wayback Machine (archive.org)
# ════════════════════════════════════════════════════════════

async def _try_wayback(url: str) -> tuple[str, str]:
    """
    Fetch the latest Internet Archive (Wayback Machine) snapshot.

    Two-step process:
      1. Call the Wayback availability API to find the most recent snapshot.
      2. Fetch the raw snapshot HTML (using the /if/ endpoint which serves
         the original HTML without the Wayback toolbar).

    Returns:
        (html, extracted_text) tuple. Both empty strings on any failure.
    """
    avail_url = f"https://archive.org/wayback/available?url={url}"
    logger.debug("Wayback Machine availability check: %s", avail_url)
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
        ) as client:
            avail_resp = await client.get(avail_url)

        if avail_resp.status_code != 200:
            logger.debug("Wayback availability API returned %d", avail_resp.status_code)
            return "", ""

        data = avail_resp.json()
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if not snapshot.get("available"):
            logger.debug("Wayback Machine: no snapshot available for %s", url)
            return "", ""

        # Use /if/ to get raw original HTML without the Wayback toolbar
        snapshot_url = snapshot["url"].replace(
            "web.archive.org/web/", "web.archive.org/web/"
        )
        # Insert /if/ flag: .../web/20240101120000/https://...
        #                → .../web/20240101120000if_/https://...
        snapshot_url = snapshot_url.replace("/web/", "/web/", 1)
        if "/if_/" not in snapshot_url:
            snapshot_url = snapshot_url.replace(
                "/web/" + snapshot["timestamp"] + "/",
                "/web/" + snapshot["timestamp"] + "if_/",
            )

        logger.debug("Wayback Machine fetching snapshot: %s", snapshot_url)
        headers = _build_headers(snapshot_url)
        async with httpx.AsyncClient(
            headers=headers,
            timeout=settings.scraper_request_timeout,
            follow_redirects=True,
        ) as client:
            snap_resp = await client.get(snapshot_url)

        if snap_resp.status_code != 200:
            logger.debug("Wayback snapshot returned HTTP %d", snap_resp.status_code)
            return "", ""

        html = snap_resp.text or ""

        # Prefer structured data from the archived HTML
        structured = _try_recipe_scrapers(url, html)
        if len(structured) >= _MIN_TEXT_LENGTH:
            logger.debug("Wayback Machine: recipe-scrapers succeeded (%d chars)", len(structured))
            return html, structured

        from bs4 import BeautifulSoup as _BS
        soup = _BS(html, "lxml")
        title_tag = soup.find("h1")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        bs4_text = _extract_text_from_html(html)
        if page_title and not bs4_text.startswith("Title:"):
            bs4_text = f"Title: {page_title}\n{bs4_text}"

        return html, bs4_text

    except Exception as exc:
        logger.debug("Wayback Machine failed for %s: %s", url, exc)
        return "", ""


# ════════════════════════════════════════════════════════════
# Strategy 5 — Playwright headless browser
# ════════════════════════════════════════════════════════════

async def _try_playwright(url: str) -> tuple[str, str]:
    """
    Fetch a page using a full headless Chromium browser via Playwright.

    Executes JavaScript, passes navigator checks, handles cookie banners
    and waits for network idle before extracting content.

    Requires:
        pip install playwright
        playwright install chromium   # downloads ~130 MB Chromium binary

    Returns:
        (html, extracted_text, error_detail) tuple.
        html and text are empty strings on any failure;
        error_detail carries a human-readable reason.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.warning("playwright package not installed — skipping Strategy 5")
        return "", ""

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                java_script_enabled=True,
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,*/*;q=0.8"
                    ),
                },
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            response = await page.goto(
                url,
                wait_until="domcontentloaded",   # faster than networkidle
                timeout=settings.scraper_request_timeout * 1000,
            )

            if response is None or response.status not in (200, 201):
                status = response.status if response else "none"
                logger.warning("Playwright got HTTP %s for %s", status, url)
                await browser.close()
                return "", ""

            await asyncio.sleep(2)   # let lazy JS content settle
            html = await page.content()
            await browser.close()

        structured = _try_recipe_scrapers(url, html)
        if len(structured) >= _MIN_TEXT_LENGTH:
            return html, structured

        text = _extract_text_from_html(html)
        return html, text

    except Exception as exc:
        logger.warning("Playwright failed for %s: %s", url, exc)
        return "", ""


# ════════════════════════════════════════════════════════════
# Public interface
# ════════════════════════════════════════════════════════════

async def scrape_url(url: str) -> str:
    """
    Fetch a recipe blog URL and extract its textual content.

    Tries five strategies in order, returning the first result with
    sufficient text content (≥ 150 characters):

      1. httpx + recipe-scrapers — structured JSON-LD/microdata
      2. cloudscraper            — Cloudflare JS-challenge bypass
      3. Bing Cache              — public HTML cache (bypasses 402/403)
      4. Wayback Machine         — Internet Archive latest snapshot
      5. Playwright              — full headless Chromium browser

    Known bot-blocking domains (e.g. allrecipes.com) skip straight to
    Strategy 3 to avoid wasting time on strategies that always fail.

    Args:
        url: A valid http/https URL pointing to a recipe page.

    Returns:
        Cleaned text content of the page (max settings.scraper_max_text_length chars).

    Raises:
        ScrapingError: On invalid URL, persistent network errors, or when
                       all five strategies return insufficient content.
    """
    _validate_url(url)
    logger.info("Scraping URL: %s", url)

    # Small random jitter (0.3–0.8s) to avoid rate-limit fingerprinting
    await asyncio.sleep(random.uniform(0.3, 0.8))

    strategy_errors: list[str] = []
    blocked_domain = _is_known_blocked(url)

    if blocked_domain:
        logger.info(
            "Known bot-blocking domain detected (%s) — skipping httpx/cloudscraper, "
            "going straight to Google Cache.",
            urlparse(url).hostname,
        )

    # ═══════════════════════════════════════════════════════
    # Strategy 1: httpx + recipe-scrapers  (skip for blocked domains)
    # ═══════════════════════════════════════════════════════
    if not blocked_domain:
        logger.debug("Strategy 1 (httpx + recipe-scrapers) for %s", url)
        try:
            html, bs_text = await _try_httpx(url)

            if html:
                structured_text = _try_recipe_scrapers(url, html)
                if len(structured_text) >= _MIN_TEXT_LENGTH:
                    logger.info(
                        "Strategy 1 (recipe-scrapers) succeeded: %d chars from %s",
                        len(structured_text), url,
                    )
                    return structured_text

                if len(bs_text) >= _MIN_TEXT_LENGTH:
                    logger.info(
                        "Strategy 1 (httpx+BS4) succeeded: %d chars from %s",
                        len(bs_text), url,
                    )
                    return bs_text

                strategy_errors.append(
                    "Strategy 1 (httpx+BS4): page returned too little text "
                    f"({len(bs_text)} chars). Likely JavaScript-rendered."
                )

        except ScrapingError as exc:
            if any(
                keyword in exc.message
                for keyword in ("404", "timed out", "Too many redirects",
                                "Network error", "Expected HTML")
            ):
                raise
            strategy_errors.append(f"Strategy 1 (httpx): {exc.message}")
    else:
        strategy_errors.append("Strategy 1 (httpx): skipped — known bot-blocking domain.")

    # ═══════════════════════════════════════════════════════
    # Strategy 2: cloudscraper  (skip for blocked domains)
    # ═══════════════════════════════════════════════════════
    if not blocked_domain:
        logger.info("Strategy 2 (cloudscraper) for %s", url)
        cs_html, cs_text = await _try_cloudscraper(url)

        if cs_html:
            cs_structured = _try_recipe_scrapers(url, cs_html)
            if len(cs_structured) >= _MIN_TEXT_LENGTH:
                logger.info(
                    "Strategy 2 (cloudscraper+recipe-scrapers) succeeded: %d chars from %s",
                    len(cs_structured), url,
                )
                return cs_structured

            if len(cs_text) >= _MIN_TEXT_LENGTH:
                logger.info(
                    "Strategy 2 (cloudscraper+BS4) succeeded: %d chars from %s",
                    len(cs_text), url,
                )
                return cs_text

            strategy_errors.append(
                f"Strategy 2 (cloudscraper): returned only {len(cs_text)} chars."
            )
        else:
            strategy_errors.append("Strategy 2 (cloudscraper): returned no content.")
    else:
        strategy_errors.append("Strategy 2 (cloudscraper): skipped — known bot-blocking domain.")

    # ═══════════════════════════════════════════════════════
    # Strategy 3: Bing Cache  (first for blocked domains)
    # ═══════════════════════════════════════════════════════
    logger.info("Strategy 3 (Bing Cache) for %s", url)
    bc_html, bc_text = await _try_bing_cache(url)

    if bc_html:
        if len(bc_text) >= _MIN_TEXT_LENGTH:
            logger.info(
                "Strategy 3 (Bing Cache) succeeded: %d chars from %s",
                len(bc_text), url,
            )
            return bc_text
        strategy_errors.append(
            f"Strategy 3 (Bing Cache): returned only {len(bc_text)} chars."
        )
    else:
        strategy_errors.append(
            "Strategy 3 (Bing Cache): no cached version found."
        )

    # ═══════════════════════════════════════════════════════
    # Strategy 4: Wayback Machine (archive.org)
    # ═══════════════════════════════════════════════════════
    logger.info("Strategy 4 (Wayback Machine) for %s", url)
    wb_html, wb_text = await _try_wayback(url)

    if wb_html:
        if len(wb_text) >= _MIN_TEXT_LENGTH:
            logger.info(
                "Strategy 4 (Wayback Machine) succeeded: %d chars from %s",
                len(wb_text), url,
            )
            return wb_text
        strategy_errors.append(
            f"Strategy 4 (Wayback Machine): returned only {len(wb_text)} chars."
        )
    else:
        strategy_errors.append(
            "Strategy 4 (Wayback Machine): no archived snapshot available."
        )

    # ═══════════════════════════════════════════════════════
    # Strategy 5: Playwright headless browser
    # ═══════════════════════════════════════════════════════
    logger.info("Strategy 5 (Playwright) for %s", url)
    pw_html, pw_text = await _try_playwright(url)

    if pw_text and len(pw_text) >= _MIN_TEXT_LENGTH:
        logger.info(
            "Strategy 5 (Playwright) succeeded: %d chars from %s",
            len(pw_text), url,
        )
        return pw_text

    if pw_html:
        strategy_errors.append(
            f"Strategy 5 (Playwright): fetched HTML but extracted only {len(pw_text)} chars."
        )
    else:
        strategy_errors.append(
            "Strategy 5 (Playwright): browser launch failed — "
            "run 'playwright install chromium' inside the venv."
        )

    error_summary = "\n".join(f"  • {e}" for e in strategy_errors)
    raise ScrapingError(
        f"Could not extract content from: {url}\n\n"
        f"All scraping strategies failed:\n{error_summary}\n\n"
        "The page may be:\n"
        "  – Heavily bot-protected (requires a paid proxy or real browser)\n"
        "  – A JavaScript-only SPA (content loaded at runtime)\n"
        "  – Behind a login or paywall\n"
        "  – Not a recipe page\n\n"
        "Try one of these reliably scrapable recipe URLs:\n"
        "  • https://www.food.com/recipe/grilled-cheese-sandwich-14609\n"
        "  • https://www.simplyrecipes.com/recipes/homemade_pizza/\n"
        "  • https://tasty.co/recipe/the-best-chocolate-chip-cookies\n"
        "  • https://www.seriouseats.com/the-best-chocolate-chip-cookies-recipe-chocolate\n"
        "  • https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/"
    )
