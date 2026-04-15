"""
app/utils/helpers.py
─────────────────────────────────────────────────────────────
Shared utility functions used across services.

All helpers are pure functions (no side effects, no I/O) to
keep them unit-testable and reusable.
"""

import json
import re
from typing import Any


def clean_text(text: str, max_length: int = 8000) -> str:
    """
    Normalise scraped HTML text for LLM consumption.

    Steps:
    1. Collapse multiple whitespace / newlines into single spaces.
    2. Remove non-printable control characters.
    3. Truncate to max_length to fit within LLM context window.

    Args:
        text: Raw text extracted from BeautifulSoup.
        max_length: Maximum character count (default 8000).

    Returns:
        Cleaned, truncated string.
    """
    # Replace tabs and multiple spaces/newlines with a single space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove non-printable characters (keep newlines and carriage returns)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", "", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Truncate with a clear marker so the LLM knows content was cut
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[... content truncated for processing ...]"

    return text


def extract_json_from_response(raw: str) -> Any:
    """
    Robustly extract a JSON object or array from an LLM response string.

    The LLM may wrap its JSON in markdown fences (```json ... ```) or
    add preamble text like "Here is the JSON:". This function strips
    all of that and attempts to parse clean JSON.

    Args:
        raw: The raw string response from the LLM.

    Returns:
        Parsed Python object (dict or list).

    Raises:
        ValueError: If no valid JSON is found in the response.
    """
    if not raw:
        raise ValueError("LLM returned an empty response.")

    # Remove markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")

    # Try direct parse first (best case: LLM returned clean JSON)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # Fall back: find the first { ... } or [ ... ] block
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Found JSON-like block but failed to parse it: {exc}"
            ) from exc

    raise ValueError(
        f"No valid JSON found in LLM response. Raw output (first 500 chars): {raw[:500]}"
    )


def safe_int(value: Any, default: int | None = None) -> int | None:
    """
    Safely convert a value to int, returning default on failure.

    Useful for parsing LLM-returned servings or calorie numbers that
    may occasionally be strings like "4 servings".
    """
    if value is None:
        return default
    try:
        # Strip non-numeric suffix (e.g. "4 servings" → 4)
        numeric = re.sub(r"[^\d].*", "", str(value).strip())
        return int(numeric) if numeric else default
    except (ValueError, TypeError):
        return default


def normalise_difficulty(value: str | None) -> str:
    """
    Normalise LLM difficulty output to one of: easy, medium, hard.

    The LLM may return values like "Easy", "MEDIUM", "moderately hard", etc.
    """
    if not value:
        return "medium"

    lower = value.lower().strip()
    if "easy" in lower or "simple" in lower or "beginner" in lower:
        return "easy"
    if "hard" in lower or "difficult" in lower or "advanced" in lower or "complex" in lower:
        return "hard"
    return "medium"


def build_ingredient_text(ingredients: list[dict]) -> str:
    """
    Convert a list of ingredient dicts into a human-readable string.

    Used when passing ingredients to downstream LLM prompts.

    Args:
        ingredients: List of { quantity, unit, item } dicts.

    Returns:
        Multi-line string, one ingredient per line.
    """
    lines = []
    for ing in ingredients:
        qty = ing.get("quantity", "")
        unit = ing.get("unit", "")
        item = ing.get("item", "")
        parts = [p for p in [qty, unit, item] if p]
        lines.append(" ".join(parts))
    return "\n".join(lines)
