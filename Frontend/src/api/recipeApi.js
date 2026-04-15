// src/api/recipeApi.js
// Native fetch-based API client — no external dependencies.

const BASE_URL = 'https://recipe-ai-1-fc1o.onrender.com/api/v1'

/**
 * Normalise error responses from the FastAPI backend.
 * Backend returns: { error: string, detail: string|null, status_code: int }
 */
async function handleResponse(res) {
  if (!res.ok) {
    let errorMessage = `HTTP ${res.status}`
    try {
      const data = await res.json()
      errorMessage = data.detail || data.error || errorMessage
    } catch {
      // non-JSON error body
    }
    throw new Error(errorMessage)
  }
  return res.json()
}

/**
 * POST /api/v1/recipes/extract
 * Extract a recipe from a given URL using the LLM pipeline.
 * @param {string} url - Full http/https recipe URL
 * @returns {Promise<RecipeResponse>}
 */
export async function extractRecipe(url) {
  const res = await fetch(`${BASE_URL}/recipes/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  return handleResponse(res)
}

/**
 * GET /api/v1/recipes/
 * List all saved recipes for the history table.
 * @returns {Promise<{ total: number, recipes: RecipeListItem[] }>}
 */
export async function listRecipes() {
  const res = await fetch(`${BASE_URL}/recipes/`)
  return handleResponse(res)
}

/**
 * GET /api/v1/recipes/{id}
 * Get full recipe detail by ID (used in modal).
 * @param {number} id - Recipe database ID
 * @returns {Promise<RecipeResponse>}
 */
export async function getRecipeById(id) {
  const res = await fetch(`${BASE_URL}/recipes/${id}`)
  return handleResponse(res)
}
