"""
app/services/llm_service.py
─────────────────────────────────────────────────────────────
LangChain + NVIDIA AI Endpoints LLM service.

All prompt templates are loaded from the prompts/ directory at
startup — never hardcoded in source. This allows prompt
iteration without code changes.

Each public function is async and corresponds to one stage of
the recipe enrichment pipeline. The service is designed to be
called with asyncio.gather() for parallelism.

Design decisions:
- ChatNVIDIA client is a module-level singleton (lazy-init to
  avoid import-time API validation failures).
- JSON output is enforced via explicit prompt instructions +
  post-processing with extract_json_from_response().
- tenacity retry logic handles transient API errors (rate
  limits, 5xx) without crashing the pipeline.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.middleware.error_handler import LLMError
from app.utils.helpers import (
    build_ingredient_text,
    extract_json_from_response,
    normalise_difficulty,
    safe_int,
)

logger = logging.getLogger(__name__)

# ── Path to the prompts/ directory ──────────────────────────
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


# ════════════════════════════════════════════════════════════
# Prompt loader (cached to avoid repeated disk I/O)
# ════════════════════════════════════════════════════════════

@lru_cache(maxsize=10)
def _load_prompt(filename: str) -> str:
    """
    Load and cache a prompt template from the prompts/ directory.

    Args:
        filename: Name of the .txt file (e.g. "recipe_extraction.txt").

    Returns:
        Contents of the prompt file as a string.

    Raises:
        LLMError: If the file is missing (config error).
    """
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise LLMError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════
# LLM client (lazy singleton)
# ════════════════════════════════════════════════════════════

_llm_client: Optional[ChatNVIDIA] = None


def _get_llm() -> ChatNVIDIA:
    """
    Return the shared ChatNVIDIA client, initialising it on first call.

    Using a module-level singleton avoids creating a new client (and
    performing auth handshake) for every LLM call.
    """
    global _llm_client
    if _llm_client is None:
        logger.info("Initialising ChatNVIDIA client (model: %s)", settings.llm_model_name)
        _llm_client = ChatNVIDIA(
            model=settings.llm_model_name,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    return _llm_client


# ════════════════════════════════════════════════════════════
# Internal LLM call helper
# ════════════════════════════════════════════════════════════

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _call_llm(prompt: str) -> str:
    """
    Send a single prompt to the LLM and return the raw text response.

    Wraps the synchronous LangChain invoke() in asyncio.to_thread()
    so it doesn't block the async event loop.

    Retries up to 3 times with exponential backoff on any exception
    (handles transient rate limits and API 5xx errors).

    Args:
        prompt: The fully-formatted prompt string.

    Returns:
        Raw text content of the LLM response.

    Raises:
        LLMError: If all retry attempts fail.
    """
    llm = _get_llm()
    messages = [
        SystemMessage(content=(
            "You are a precise data extraction assistant. "
            "Always respond with valid JSON only — no markdown, no explanation."
        )),
        HumanMessage(content=prompt),
    ]
    try:
        # Run synchronous LangChain call in a thread to avoid blocking
        response = await asyncio.to_thread(llm.invoke, messages)
        return response.content
    except Exception as exc:
        logger.warning("LLM call failed (will retry): %s", exc)
        raise


async def _call_llm_safe(prompt: str, context: str = "") -> Any:
    """
    Call the LLM and parse the JSON response, raising LLMError on failure.

    Args:
        prompt: Formatted prompt string.
        context: Label for error logging (e.g. "recipe extraction").

    Returns:
        Parsed Python object (dict or list).

    Raises:
        LLMError: On LLM API failure or unparseable JSON response.
    """
    try:
        raw = await _call_llm(prompt)
        return extract_json_from_response(raw)
    except Exception as exc:
        raise LLMError(f"LLM call failed during {context}: {exc}") from exc


# ════════════════════════════════════════════════════════════
# Public LLM pipeline functions
# ════════════════════════════════════════════════════════════

async def extract_recipe(text: str) -> Dict[str, Any]:
    """
    Extract structured recipe data from raw scraped text.

    Uses the recipe_extraction.txt prompt. The LLM returns a JSON
    object with title, cuisine, times, servings, difficulty, ingredients,
    and instructions.

    Args:
        text: Cleaned scraped text from the recipe blog page.

    Returns:
        Dict with recipe fields. Difficulty is normalised.

    Raises:
        LLMError: On API failure or bad LLM response.
    """
    template = _load_prompt("recipe_extraction.txt")
    prompt = template.format(recipe_text=text)

    logger.info("Calling LLM: recipe extraction")
    result = await _call_llm_safe(prompt, context="recipe extraction")

    if not isinstance(result, dict):
        raise LLMError("Recipe extraction returned non-dict JSON.")

    # Normalise difficulty to one of: easy / medium / hard
    result["difficulty"] = normalise_difficulty(result.get("difficulty"))

    # Normalise servings to int
    result["servings"] = safe_int(result.get("servings"))

    return result


async def generate_nutrition(title: str, servings: Optional[int], ingredients: List[Dict]) -> Dict:
    """
    Generate a per-serving nutritional estimate for a recipe.

    Args:
        title: Recipe title (provides context to the LLM).
        servings: Number of servings (used for per-serving calculation).
        ingredients: List of {quantity, unit, item} dicts.

    Returns:
        Dict with calories (int), protein, carbs, fat (strings ending in "g").

    Raises:
        LLMError: On API failure or bad LLM response.
    """
    template = _load_prompt("nutrition_estimation.txt")
    ingredients_text = build_ingredient_text(ingredients)
    prompt = template.format(
        title=title or "Unknown Recipe",
        servings=servings or "unknown",
        ingredients_text=ingredients_text,
    )

    logger.info("Calling LLM: nutrition estimation")
    result = await _call_llm_safe(prompt, context="nutrition estimation")

    if not isinstance(result, dict):
        raise LLMError("Nutrition estimation returned non-dict JSON.")

    # Ensure calories is an integer
    if "calories" in result:
        result["calories"] = safe_int(result["calories"])

    return result


async def generate_substitutions(title: str, cuisine: Optional[str], ingredients: List[Dict]) -> List[str]:
    """
    Generate 3 practical ingredient substitution suggestions.

    Args:
        title: Recipe title.
        cuisine: Cuisine type (provides context).
        ingredients: List of {quantity, unit, item} dicts.

    Returns:
        List of exactly 3 substitution strings.

    Raises:
        LLMError: On API failure or bad LLM response.
    """
    template = _load_prompt("substitutions.txt")
    ingredients_text = build_ingredient_text(ingredients)
    prompt = template.format(
        title=title or "Unknown Recipe",
        cuisine=cuisine or "Unknown",
        ingredients_text=ingredients_text,
    )

    logger.info("Calling LLM: substitutions")
    result = await _call_llm_safe(prompt, context="substitutions")

    if not isinstance(result, list):
        raise LLMError("Substitutions returned non-list JSON.")

    return [str(s) for s in result[:3]]  # enforce max 3


async def generate_shopping_list(ingredients: List[Dict]) -> Dict[str, List[str]]:
    """
    Group ingredients into a categorised shopping list.

    Args:
        ingredients: List of {quantity, unit, item} dicts.

    Returns:
        Dict mapping category names to lists of ingredient item names.

    Raises:
        LLMError: On API failure or bad LLM response.
    """
    template = _load_prompt("shopping_list.txt")
    ingredients_text = build_ingredient_text(ingredients)
    prompt = template.format(ingredients_text=ingredients_text)

    logger.info("Calling LLM: shopping list")
    result = await _call_llm_safe(prompt, context="shopping list")

    if not isinstance(result, dict):
        raise LLMError("Shopping list returned non-dict JSON.")

    # Ensure all values are lists of strings
    return {
        category: [str(item) for item in items]
        for category, items in result.items()
        if isinstance(items, list)
    }


async def generate_related_recipes(
    title: str, cuisine: Optional[str], difficulty: Optional[str], ingredients: List[Dict]
) -> List[str]:
    """
    Suggest 3 recipes that pair well with or complement this dish.

    Args:
        title: Recipe title.
        cuisine: Cuisine type.
        difficulty: Difficulty level.
        ingredients: List of ingredient dicts (top 5 used as key ingredients).

    Returns:
        List of exactly 3 recipe name strings.

    Raises:
        LLMError: On API failure or bad LLM response.
    """
    template = _load_prompt("related_recipes.txt")

    # Use up to 5 key ingredients as context
    key_items = [ing.get("item", "") for ing in ingredients[:5]]
    key_ingredients = ", ".join(key_items) if key_items else "various ingredients"

    prompt = template.format(
        title=title or "Unknown Recipe",
        cuisine=cuisine or "Unknown",
        difficulty=difficulty or "medium",
        key_ingredients=key_ingredients,
    )

    logger.info("Calling LLM: related recipes")
    result = await _call_llm_safe(prompt, context="related recipes")

    if not isinstance(result, list):
        raise LLMError("Related recipes returned non-list JSON.")

    return [str(r) for r in result[:3]]  # enforce max 3
