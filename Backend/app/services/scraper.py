"""
app/services/scraper.py
─────────────────────────────────────────────────────────────
Async web scraper for recipe blog pages.

Strategy cascade (tried in order, first success wins):

  1. recipe-scrapers (JSON-LD / microdata)
     Uses the `recipe-scrapers` library which reads structured
     Schema.org/Recipe markup embedded in the page.  Works on
     the vast majority of modern recipe sites — including many
     Cloudflare-protected ones — because the structured data is
     rendered server-side. Returns a richly formatted text block.

  2. cloudscraper (Cloudflare JS-challenge bypass)
     Falls back to `cloudscraper` which emulates a real browser
     TLS fingerprint to pass Cloudflare's JS challenge.  The
     returned HTML is then parsed by BeautifulSoup exactly as in
     strategy 3.

  3. httpx + BeautifulSoup (plain HTML scraping)
     Final fallback.  Sends realistic browser-like headers and
     parses the raw HTML with BeautifulSoup.  Works fine for
     sites without bot-detection.

All three strategies share the same URL validation and text
cleaning utilities.  The first strategy that returns ≥ 150
characters of cleaned text is used; if all three fail, a
ScrapingError is raised with a combined diagnostic message.
"""

import asyncio
import logging
import random
from urllib.parse import urlparse

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

# ── Minimum text length to consider a scrape successful ─────
_MIN_TEXT_LENGTH = 150


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
        from recipe_scrapers import scrape_html

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

            cs = cloudscraper.create_scraper(
                browser={
                    "browser": "chrome",
                    "platform": "windows",
                    "mobile": False,
                }
            )
            resp = cs.get(url, timeout=settings.scraper_request_timeout)
            if resp.status_code != 200:
                logger.debug(
                    "cloudscraper got HTTP %d for %s", resp.status_code, url
                )
                return "", ""
            html = resp.text
            return html, _extract_text_from_html(html)
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
    headers = _build_headers(url)

    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=settings.scraper_request_timeout,
            follow_redirects=True,
            cookies={},
        ) as client:
            response = await client.get(url)

    except httpx.TimeoutException:
        raise ScrapingError(
            f"Request timed out after {settings.scraper_request_timeout}s. "
            "The site may be slow or blocking automated access."
        )
    except httpx.TooManyRedirects:
        raise ScrapingError(f"Too many redirects for URL: {url}")
    except httpx.RequestError as exc:
        raise ScrapingError(f"Network error while fetching '{url}': {exc}") from exc

    # HTTP error handling
    if response.status_code == 404:
        raise ScrapingError(f"Page not found (HTTP 404): {url}")
    if response.status_code == 429:
        raise ScrapingError(
            "Rate limited (HTTP 429). The site is throttling requests. "
            "Please wait a moment and try again."
        )
    if response.status_code == 403:
        # Don't raise here — let cloudscraper handle it in strategy 2
        logger.debug("httpx got 403 for %s — will try cloudscraper", url)
        return "", ""
    if response.status_code not in (200, 201):
        raise ScrapingError(
            f"Unexpected HTTP {response.status_code} from {url}"
        )

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise ScrapingError(
            f"Expected HTML but received '{content_type}'. "
            "This URL may point to a PDF, image, or API endpoint."
        )

    html = response.text
    text = _extract_text_from_html(html)
    return html, text


# ════════════════════════════════════════════════════════════
# Public interface
# ════════════════════════════════════════════════════════════

async def scrape_url(url: str) -> str:
    """
    Fetch a recipe blog URL and extract its textual content.

    Tries three strategies in order, returning the first result with
    sufficient text content (≥ 150 characters):

      1. recipe-scrapers — structured JSON-LD/microdata extraction
      2. cloudscraper    — Cloudflare JS-challenge bypass
      3. httpx           — plain async HTTP + BeautifulSoup

    Args:
        url: A valid http/https URL pointing to a recipe page.

    Returns:
        Cleaned text content of the page (max settings.scraper_max_text_length chars).

    Raises:
        ScrapingError: On invalid URL, persistent network errors, or when
                       all three strategies return insufficient content.
    """
    _validate_url(url)

    logger.info("Scraping URL: %s", url)

    # Small random jitter (0.3–1.0s) to avoid rate-limit fingerprinting
    await asyncio.sleep(random.uniform(0.3, 1.0))

    strategy_errors: list[str] = []

    # ── Strategy 1: httpx fetch → recipe-scrapers JSON-LD ───
    logger.debug("Strategy 1 (recipe-scrapers) for %s", url)
    try:
        html, bs_text = await _try_httpx(url)

        if html:
            # First try structured data on the fetched HTML
            structured_text = _try_recipe_scrapers(url, html)
            if len(structured_text) >= _MIN_TEXT_LENGTH:
                logger.info(
                    "Strategy 1 (recipe-scrapers) succeeded: %d chars from %s",
                    len(structured_text), url,
                )
                return structured_text

            # Fallback: use raw BeautifulSoup text from the same fetch
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
        # Network-level hard failures (404, timeout, etc.) bubble straight up
        if any(
            keyword in exc.message
            for keyword in ("404", "timed out", "Too many redirects", "Network error",
                            "Expected HTML")
        ):
            raise
        strategy_errors.append(f"Strategy 1 (httpx): {exc.message}")

    # ── Strategy 2: cloudscraper (Cloudflare bypass) ───────
    logger.info("Strategy 2 (cloudscraper) for %s", url)
    cs_html, cs_text = await _try_cloudscraper(url)

    if cs_html:
        # Try recipe-scrapers on the cloudscraper-fetched HTML first
        cs_structured = _try_recipe_scrapers(url, cs_html)
        if len(cs_structured) >= _MIN_TEXT_LENGTH:
            logger.info(
                "Strategy 2 (cloudscraper+recipe-scrapers) succeeded: %d chars from %s",
                len(cs_structured), url,
            )
            return cs_structured

        # Fall back to BeautifulSoup text from cloudscraper HTML
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


    error_summary = "\n".join(f"  • {e}" for e in strategy_errors)
    raise ScrapingError(
        f"Could not extract content from: {url}\n\n"
        f"All scraping strategies failed:\n{error_summary}\n\n"
        "The page may be:\n"
        "  – A JavaScript-only SPA (content loaded at runtime)\n"
        "  – Behind a login / paywall\n"
        "  – Not a recipe page\n\n"
        "Try one of these reliably scrapable recipe URLs:\n"
        "  • https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/\n"
        "  • https://www.food.com/recipe/grilled-cheese-sandwich-14609\n"
        "  • https://www.simplyrecipes.com/recipes/homemade_pizza/\n"
        "  • https://tasty.co/recipe/the-best-chocolate-chip-cookies\n"
        "  • https://www.seriouseats.com/the-best-chocolate-chip-cookies-recipe-chocolate"
    )
