"""
app/routes/recipe.py
─────────────────────────────────────────────────────────────
FastAPI router for recipe extraction and history endpoints.

All route handlers are thin wrappers that delegate to
recipe_service.py — no business logic lives here.

Endpoints:
  POST /api/v1/recipes/extract   — Extract a recipe from a URL
  GET  /api/v1/recipes/          — List all saved recipes (history)
  GET  /api/v1/recipes/{id}      — Get a single recipe by ID
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.recipe import (
    ErrorResponse,
    RecipeExtractRequest,
    RecipeListResponse,
    RecipeResponse,
)
from app.services import recipe_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recipes",
    tags=["Recipes"],
)


@router.post(
    "/extract",
    response_model=RecipeResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract a recipe from a blog URL",
    description=(
        "Accepts a recipe blog URL. Scrapes the page, uses an LLM to extract "
        "structured recipe data, generates nutrition estimates, substitutions, "
        "shopping list, and related recipes. Stores and returns the full recipe."
        "\n\nIf the URL was previously processed, the cached database record is "
        "returned immediately without re-scraping."
    ),
    responses={
        200: {"model": RecipeResponse, "description": "Recipe successfully extracted"},
        422: {"model": ErrorResponse, "description": "Invalid URL or scraping failure"},
        502: {"model": ErrorResponse, "description": "LLM API error"},
    },
)
async def extract_recipe(
    payload: RecipeExtractRequest,
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """
    POST /api/v1/recipes/extract

    Body: { "url": "https://..." }
    Returns the full structured recipe JSON.
    """
    logger.info("POST /recipes/extract — url=%s", payload.url)
    return await recipe_service.process_recipe(url=payload.url, db=db)


@router.get(
    "/",
    response_model=RecipeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all saved recipes",
    description=(
        "Returns a paginated list of all previously extracted recipes. "
        "Each item includes id, title, cuisine, difficulty, and date extracted. "
        "Ordered by most recently created first."
    ),
)
async def list_recipes(
    db: AsyncSession = Depends(get_db),
) -> RecipeListResponse:
    """
    GET /api/v1/recipes/

    Returns { total: int, recipes: [...] } for the history table.
    """
    logger.info("GET /recipes/ — fetching history list")
    return await recipe_service.get_all_recipes(db=db)


@router.get(
    "/{recipe_id}",
    response_model=RecipeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single recipe by ID",
    description=(
        "Returns the full structured recipe data for the given recipe ID. "
        "Used by the frontend modal when a user clicks 'Details' in the history table."
    ),
    responses={
        200: {"model": RecipeResponse, "description": "Recipe found"},
        404: {"model": ErrorResponse, "description": "Recipe not found"},
    },
)
async def get_recipe(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """
    GET /api/v1/recipes/{recipe_id}

    Returns the full recipe detail. Raises 404 if not found.
    """
    logger.info("GET /recipes/%d — fetching recipe detail", recipe_id)
    return await recipe_service.get_recipe_by_id(recipe_id=recipe_id, db=db)
