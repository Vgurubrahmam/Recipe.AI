"""
app/middleware/error_handler.py
─────────────────────────────────────────────────────────────
Custom exception classes and FastAPI exception handlers.

All API errors are surfaced as structured JSON responses so the
frontend always receives a consistent { error, detail, status_code }
shape, regardless of where the exception originated.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Custom Exception Classes
# ═══════════════════════════════════════════════════════════

class RecipeExtractorError(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ScrapingError(RecipeExtractorError):
    """
    Raised when the scraper cannot retrieve or parse the target URL.
    Examples: invalid URL, connection timeout, non-recipe page.
    """

    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class LLMError(RecipeExtractorError):
    """
    Raised when the LLM returns an unusable response.
    Examples: empty reply, malformed JSON, API quota exceeded.
    """

    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class RecipeNotFoundError(RecipeExtractorError):
    """Raised when a requested recipe ID does not exist in the database."""

    def __init__(self, recipe_id: int):
        super().__init__(f"Recipe with id={recipe_id} not found.", status_code=404)


class DuplicateURLError(RecipeExtractorError):
    """
    Raised (as an informational signal) when a URL was already processed.
    Handlers should return the cached recipe instead of HTTP 409.
    """

    def __init__(self, url: str):
        super().__init__(f"URL already processed: {url}", status_code=200)
        self.url = url


# ═══════════════════════════════════════════════════════════
# JSON helper
# ═══════════════════════════════════════════════════════════

def _error_response(error: str, detail: str | None, status_code: int) -> JSONResponse:
    """Build the standard error JSON body."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "detail": detail,
            "status_code": status_code,
        },
    )


# ═══════════════════════════════════════════════════════════
# Handler Registration
# ═══════════════════════════════════════════════════════════

def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach all custom exception handlers to the FastAPI application.
    Call this once during app creation in main.py.
    """

    @app.exception_handler(RecipeExtractorError)
    async def handle_recipe_extractor_error(
        request: Request, exc: RecipeExtractorError
    ) -> JSONResponse:
        """Handle all application-level custom exceptions."""
        logger.warning(
            "RecipeExtractorError [%s]: %s — path=%s",
            type(exc).__name__,
            exc.message,
            request.url.path,
        )
        return _error_response(
            error=type(exc).__name__,
            detail=exc.message,
            status_code=exc.status_code,
        )

    @app.exception_handler(ValidationError)
    async def handle_pydantic_validation_error(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Surface Pydantic validation failures as structured 422 responses."""
        logger.warning("ValidationError: %s", exc)
        return _error_response(
            error="ValidationError",
            detail=str(exc),
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        """Catch unchecked ValueError from service layer."""
        logger.warning("ValueError: %s", exc)
        return _error_response(
            error="BadRequest",
            detail=str(exc),
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler to prevent stack traces leaking to clients."""
        logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
        return _error_response(
            error="InternalServerError",
            detail="An unexpected error occurred. Please try again later.",
            status_code=500,
        )
