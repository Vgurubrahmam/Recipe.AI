"""
app/models/recipe.py
─────────────────────────────────────────────────────────────
SQLAlchemy ORM model for the `recipes` table.

JSONB columns store structured sub-data (ingredients, nutrition,
substitutions, shopping_list, related_recipes) — this avoids
the overhead of multiple join tables for list/dict payloads,
while still allowing efficient querying via PostgreSQL JSONB operators.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Recipe(Base):
    """
    Represents a fully processed recipe extracted from a blog URL.

    All generated fields (ingredients, nutrition, substitutions, etc.)
    are stored as JSONB so the schema is flexible without requiring
    migrations for minor LLM output changes.
    """

    __tablename__ = "recipes"

    # ── Primary key ──────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Source & identity ────────────────────────────────────
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Timing & servings ────────────────────────────────────
    prep_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cook_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Classification ───────────────────────────────────────
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── JSONB payload columns ────────────────────────────────
    # Each stores the full structured list/dict as returned by the LLM
    ingredients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    """List of {quantity, unit, item} dicts."""

    instructions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    """Ordered list of step strings."""

    nutrition_estimate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """{ calories, protein, carbs, fat }"""

    substitutions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    """List of substitution suggestion strings."""

    shopping_list: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """{ category: [items] } grouped shopping list."""

    related_recipes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    """List of related recipe name strings."""

    # ── Raw scrape content (for debugging / re-processing) ──
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Audit ────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Recipe id={self.id} title={self.title!r} url={self.url!r}>"
