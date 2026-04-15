"""
app/schemas/recipe.py
─────────────────────────────────────────────────────────────
Pydantic v2 request/response schemas for the Recipe API.

These schemas serve as the contract between the frontend and
the backend — they validate input, document the API via
OpenAPI, and shape the JSON output.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, HttpUrl, field_validator, model_validator


# ═══════════════════════════════════════════════════════════
# Sub-schemas (reusable building blocks)
# ═══════════════════════════════════════════════════════════

class IngredientSchema(BaseModel):
    """A single ingredient broken into quantity, unit, and item."""

    quantity: str
    unit: str
    item: str

    model_config = {"from_attributes": True}

    @field_validator("quantity", "unit", "item", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> str:
        """Coerce numeric/None LLM outputs to strings gracefully."""
        if v is None:
            return ""
        return str(v)


class NutritionSchema(BaseModel):
    """Approximate per-serving nutritional values."""

    calories: Optional[int] = None
    protein: Optional[str] = None
    carbs: Optional[str] = None
    fat: Optional[str] = None

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
# Request Schemas
# ═══════════════════════════════════════════════════════════

class RecipeExtractRequest(BaseModel):
    """
    Input payload for POST /api/v1/recipes/extract.
    Accepts any valid HTTP/HTTPS URL pointing to a recipe blog.
    """

    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure the URL has a valid HTTP/HTTPS scheme."""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL exceeds maximum length of 2048 characters")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/"
            }
        }
    }


# ═══════════════════════════════════════════════════════════
# Response Schemas
# ═══════════════════════════════════════════════════════════

class RecipeResponse(BaseModel):
    """
    Full recipe response returned by POST /extract and GET /{id}.
    Matches the sample JSON output defined in the project spec.
    """

    id: int
    url: str
    title: Optional[str] = None
    cuisine: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    total_time: Optional[str] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None

    # Structured sub-data
    ingredients: Optional[List[IngredientSchema]] = None
    instructions: Optional[List[str]] = None
    nutrition_estimate: Optional[NutritionSchema] = None
    substitutions: Optional[List[str]] = None
    shopping_list: Optional[Dict[str, List[str]]] = None
    related_recipes: Optional[List[str]] = None

    @field_validator("servings", mode="before")
    @classmethod
    def coerce_servings(cls, v: Any) -> Optional[int]:
        """Accept string servings like '4 servings' or numeric from LLM."""
        if v is None:
            return None
        try:
            # Handle strings like '4 servings', '4-6'
            return int(str(v).split()[0].split("-")[0])
        except (ValueError, IndexError):
            return None

    @field_validator("ingredients", mode="before")
    @classmethod
    def filter_invalid_ingredients(cls, v: Any) -> Any:
        """Drop any ingredient entries that are not dicts (LLM noise)."""
        if not isinstance(v, list):
            return v
        return [item for item in v if isinstance(item, dict)]

    @field_validator("instructions", "substitutions", "related_recipes", mode="before")
    @classmethod
    def coerce_str_list(cls, v: Any) -> Any:
        """Coerce list items to strings, drop None entries."""
        if not isinstance(v, list):
            return v
        return [str(item) for item in v if item is not None]

    created_at: datetime

    model_config = {
        "from_attributes": True,  # Allow building from SQLAlchemy ORM objects
        "json_schema_extra": {
            "example": {
                "id": 1,
                "url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/",
                "title": "Classic Grilled Cheese Sandwich",
                "cuisine": "American",
                "prep_time": "5 mins",
                "cook_time": "10 mins",
                "total_time": "15 mins",
                "servings": 2,
                "difficulty": "easy",
                "ingredients": [
                    {"quantity": "4", "unit": "slices", "item": "white bread"},
                    {"quantity": "2", "unit": "slices", "item": "cheddar cheese"},
                    {"quantity": "2", "unit": "tbsp", "item": "butter"},
                ],
                "instructions": [
                    "Butter one side of each bread slice.",
                    "Place cheese between two slices, butter side facing out.",
                    "Heat a skillet over medium heat.",
                    "Cook sandwich 3-4 minutes per side until golden brown.",
                    "Slice and serve hot.",
                ],
                "nutrition_estimate": {
                    "calories": 350,
                    "protein": "12g",
                    "carbs": "30g",
                    "fat": "20g",
                },
                "substitutions": [
                    "Replace butter with olive oil for a dairy-free option.",
                    "Use whole wheat bread instead of white bread for more fiber.",
                    "Swap cheddar with mozzarella for a milder cheese.",
                ],
                "shopping_list": {
                    "dairy": ["cheddar cheese", "butter"],
                    "bakery": ["white bread"],
                },
                "related_recipes": [
                    "Tomato Soup",
                    "French Onion Grilled Cheese",
                    "Caprese Sandwich",
                ],
                "created_at": "2024-01-15T10:30:00Z",
            }
        },
    }


class RecipeListItem(BaseModel):
    """
    Compact recipe representation for the history table (Tab 2).
    Does NOT include ingredients / instructions to keep the list fast.
    """

    id: int
    url: str
    title: Optional[str] = None
    cuisine: Optional[str] = None
    difficulty: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecipeListResponse(BaseModel):
    """Paginated wrapper for recipe history list."""

    total: int
    recipes: List[RecipeListItem]


# ═══════════════════════════════════════════════════════════
# Error Schema
# ═══════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    detail: Optional[str] = None
    status_code: int
