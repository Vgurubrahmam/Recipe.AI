"""
app/services/recipe_service.py
─────────────────────────────────────────────────────────────
Orchestration layer: coordinates scraping, LLM calls, and
database persistence for the full recipe extraction pipeline.

This module is the single point of truth for the business logic.
Routes only call functions here — they never interact with the
scraper, LLM service, or DB directly.

Key behaviours:
- URL deduplication: if a URL was already processed, the cached
  DB record is returned immediately (no re-scraping or LLM calls).
- Parallel LLM enrichment: nutrition, substitutions, shopping list,
  and related recipes are generated concurrently via asyncio.gather()
  to minimise total latency.
- Partial failure tolerance: if one enrichment call fails, the
  others still succeed and the recipe is saved with null for the
  failed field.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import LLMError, RecipeNotFoundError
from app.models.recipe import Recipe
from app.schemas.recipe import RecipeListItem, RecipeListResponse, RecipeResponse
from app.services import llm_service, scraper

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════

def _orm_to_response(recipe: Recipe) -> RecipeResponse:
    """
    Convert a Recipe ORM instance into a RecipeResponse Pydantic model.

    Handles the ingredient and nutrition JSONB fields which may contain
    plain dicts rather than Pydantic sub-model instances.
    """
    return RecipeResponse(
        id=recipe.id,
        url=recipe.url,
        title=recipe.title,
        cuisine=recipe.cuisine,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=recipe.total_time,
        servings=recipe.servings,
        difficulty=recipe.difficulty,
        ingredients=recipe.ingredients or [],
        instructions=recipe.instructions or [],
        nutrition_estimate=recipe.nutrition_estimate,
        substitutions=recipe.substitutions or [],
        shopping_list=recipe.shopping_list or {},
        related_recipes=recipe.related_recipes or [],
        created_at=recipe.created_at,
    )


async def _safe_enrich(coro, field_name: str) -> Any:
    """
    Run an async enrichment coroutine and return None on failure.

    This allows partial failures in the enrichment phase without
    aborting the entire recipe extraction pipeline. The failed
    field will be stored as null in the database.

    Args:
        coro: Awaitable coroutine for a single enrichment task.
        field_name: Human-readable name for logging (e.g. "nutrition").

    Returns:
        The coroutine result, or None if it raised any exception.
    """
    try:
        return await coro
    except Exception as exc:
        logger.warning("Enrichment failed for '%s': %s", field_name, exc)
        return None


# ════════════════════════════════════════════════════════════
# Public service functions
# ════════════════════════════════════════════════════════════

async def process_recipe(url: str, db: AsyncSession) -> RecipeResponse:
    """
    Full recipe extraction pipeline for a given URL.

    Steps:
    1. Check if URL already exists in the database (return cached).
    2. Scrape the page content with BeautifulSoup.
    3. Extract structured recipe data via LLM (title, ingredients, etc.).
    4. Run nutrition, substitutions, shopping list, and related recipe
       generation concurrently via asyncio.gather().
    5. Persist the complete record to PostgreSQL.
    6. Return the full RecipeResponse.

    Args:
        url: A validated HTTP/HTTPS recipe blog URL.
        db: Active async database session (injected via FastAPI Depends).

    Returns:
        RecipeResponse with all extracted and generated fields.

    Raises:
        ScrapingError: If the URL cannot be fetched or parsed.
        LLMError: If recipe extraction fails (enrichment failures are tolerated).
    """
    # ── Step 1: URL deduplication ────────────────────────────
    existing = await db.scalar(select(Recipe).where(Recipe.url == url))
    if existing:
        logger.info("Cache hit — returning existing recipe for URL: %s", url)
        return _orm_to_response(existing)

    # ── Step 2: Scrape ───────────────────────────────────────
    logger.info("Starting recipe extraction pipeline for: %s", url)
    raw_text = await scraper.scrape_url(url)

    # ── Step 3: Core LLM extraction ──────────────────────────
    # This is the critical step — if it fails, the whole pipeline stops
    recipe_data = await llm_service.extract_recipe(raw_text)

    title = recipe_data.get("title")
    cuisine = recipe_data.get("cuisine")
    difficulty = recipe_data.get("difficulty")
    servings = recipe_data.get("servings")
    ingredients = recipe_data.get("ingredients") or []

    # ── Step 4: Parallel enrichment ──────────────────────────
    # All four enrichment tasks run concurrently to minimise latency
    logger.info("Running parallel enrichment for: %s", title)
    nutrition, substitutions, shopping_list, related_recipes = await asyncio.gather(
        _safe_enrich(
            llm_service.generate_nutrition(title, servings, ingredients),
            "nutrition",
        ),
        _safe_enrich(
            llm_service.generate_substitutions(title, cuisine, ingredients),
            "substitutions",
        ),
        _safe_enrich(
            llm_service.generate_shopping_list(ingredients),
            "shopping_list",
        ),
        _safe_enrich(
            llm_service.generate_related_recipes(title, cuisine, difficulty, ingredients),
            "related_recipes",
        ),
    )

    # ── Step 5: Persist to database ──────────────────────────
    db_recipe = Recipe(
        url=url,
        title=title,
        cuisine=cuisine,
        prep_time=recipe_data.get("prep_time"),
        cook_time=recipe_data.get("cook_time"),
        total_time=recipe_data.get("total_time"),
        servings=servings,
        difficulty=difficulty,
        ingredients=ingredients,
        instructions=recipe_data.get("instructions") or [],
        nutrition_estimate=nutrition,
        substitutions=substitutions,
        shopping_list=shopping_list,
        related_recipes=related_recipes,
        raw_text=raw_text,
    )

    db.add(db_recipe)
    await db.flush()   # Get the auto-generated ID before commit
    await db.refresh(db_recipe)

    logger.info("Recipe saved to DB with id=%d: %s", db_recipe.id, title)
    return _orm_to_response(db_recipe)


async def get_all_recipes(db: AsyncSession) -> RecipeListResponse:
    """
    Retrieve a summary list of all saved recipes for the history table.

    Returns recipes ordered by creation date (newest first).
    Only the fields needed for the table row are fetched.

    Args:
        db: Active async database session.

    Returns:
        RecipeListResponse containing total count and list of RecipeListItems.
    """
    result = await db.execute(
        select(Recipe).order_by(Recipe.created_at.desc())
    )
    recipes = result.scalars().all()

    items = [
        RecipeListItem(
            id=r.id,
            url=r.url,
            title=r.title,
            cuisine=r.cuisine,
            difficulty=r.difficulty,
            created_at=r.created_at,
        )
        for r in recipes
    ]

    return RecipeListResponse(total=len(items), recipes=items)


async def get_recipe_by_id(recipe_id: int, db: AsyncSession) -> RecipeResponse:
    """
    Retrieve a single recipe by its database ID.

    Args:
        recipe_id: Integer primary key.
        db: Active async database session.

    Returns:
        Full RecipeResponse (same shape as the extract endpoint).

    Raises:
        RecipeNotFoundError: If no recipe with this ID exists.
    """
    recipe = await db.scalar(select(Recipe).where(Recipe.id == recipe_id))
    if not recipe:
        raise RecipeNotFoundError(recipe_id)
    return _orm_to_response(recipe)
