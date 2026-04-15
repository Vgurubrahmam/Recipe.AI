# Recipe Extractor & Meal Planner

A full-stack AI-powered application that scrapes recipe blog URLs, uses NVIDIA LLMs to extract structured recipe data, and presents everything through a modern React + shadcn/ui frontend.

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL (Supabase / Docker) + SQLAlchemy asyncpg |
| LLM | NVIDIA AI Endpoints — `meta/llama-3.1-70b-instruct` via LangChain |
| Scraping | `recipe-scrapers` (JSON-LD) → `cloudscraper` (Cloudflare bypass) → `httpx` + BeautifulSoup4 |
| Config | pydantic-settings (.env) |
| Migrations | Alembic |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 19 + Vite 8 |
| UI Components | shadcn/ui (Radix UI primitives) |
| Styling | Tailwind CSS v3 + CSS Variables (dark slate theme) |
| Icons | Lucide React |
| API | Native `fetch` (no Axios) |

---

## Project Structure

```
Recipe Extractor & Meal Planner/
├── Backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, lifespan, routers
│   │   ├── config.py                # pydantic-settings (.env loader)
│   │   ├── database.py              # Async SQLAlchemy engine & session
│   │   ├── models/recipe.py         # Recipe ORM model (JSONB columns)
│   │   ├── schemas/recipe.py        # Pydantic request/response schemas
│   │   ├── routes/recipe.py         # POST /extract, GET /, GET /{id}
│   │   ├── services/
│   │   │   ├── scraper.py           # 3-strategy scraping cascade
│   │   │   ├── llm_service.py       # LangChain + NVIDIA AI pipeline
│   │   │   └── recipe_service.py    # Orchestration: scrape → LLM → DB
│   │   ├── middleware/error_handler.py
│   │   └── utils/helpers.py
│   ├── prompts/                     # External LLM prompt templates
│   │   ├── recipe_extraction.txt
│   │   ├── nutrition_estimation.txt
│   │   ├── substitutions.txt
│   │   ├── shopping_list.txt
│   │   └── related_recipes.txt
│   ├── sample_data/
│   ├── alembic/
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env                         # Your secrets (never commit)
│   └── .env.example
│
└── Frontend/
    ├── src/
    │   ├── api/recipeApi.js          # fetch-based API client
    │   ├── components/
    │   │   ├── ui/                  # shadcn/ui primitives
    │   │   ├── RecipeCard.jsx
    │   │   ├── RecipeModal.jsx
    │   │   ├── NutritionBadge.jsx
    │   │   ├── IngredientList.jsx
    │   │   ├── InstructionSteps.jsx
    │   │   ├── ShoppingList.jsx
    │   │   └── LoadingSpinner.jsx
    │   ├── pages/
    │   │   ├── ExtractTab.jsx
    │   │   └── HistoryTab.jsx
    │   ├── lib/utils.js              # cn() Tailwind merge utility
    │   ├── App.jsx
    │   └── index.css
    ├── vite.config.js               # /api proxy → localhost:8000
    ├── tailwind.config.js
    └── components.json              # shadcn/ui config
```

---

## Backend Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (Supabase recommended, or Docker)
- NVIDIA AI Endpoints API key → [build.nvidia.com](https://build.nvidia.com/)

### Step 1 — Configure environment variables

```bash
cd Backend
copy .env.example .env
```

Edit `.env` with your actual values (see [Environment Variables](#environment-variables) section below).

### Step 2 — Create virtual environment & install dependencies

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

### Step 3 — Database setup

**Option A — Supabase (recommended for production)**
Set `DATABASE_URL` in `.env` to your Supabase session-mode pooler URL:
```
postgresql+asyncpg://<user>:<password>@<host>:5432/postgres
```

**Option B — Docker local PostgreSQL**
```bash
docker-compose up -d
```
Then set:
```
DATABASE_URL=postgresql+asyncpg://recipe_user:recipe_pass@localhost:5432/recipe_db
```

### Step 4 — Run migrations

```bash
alembic upgrade head
```

### Step 5 — Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API running at `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

---

## Frontend Setup

### Prerequisites
- Node.js 18+

### Step 1 — Install dependencies

```bash
cd Frontend
npm install
```

### Step 2 — Start the dev server

```bash
npm run dev
```

Frontend running at `http://localhost:5173`

> The Vite dev server proxies `/api/*` → `http://localhost:8000` automatically. No CORS config needed in development.

---

## API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/recipes/extract` | Extract recipe from URL (scrape + LLM pipeline) |
| `GET` | `/recipes/` | List all saved recipes (history table) |
| `GET` | `/recipes/{id}` | Full recipe detail by ID (for modal) |
| `GET` | `/health` | Health check |

---

### `POST /api/v1/recipes/extract`

**Request:**
```json
{ "url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/" }
```

**Response (200) — all 15 fields:**
```json
{
  "id": 1,
  "url": "https://...",
  "title": "Classic Grilled Cheese Sandwich",
  "cuisine": "American",
  "prep_time": "5 mins",
  "cook_time": "10 mins",
  "total_time": "15 mins",
  "servings": 2,
  "difficulty": "easy",
  "ingredients": [
    { "quantity": "4", "unit": "slices", "item": "white bread" },
    { "quantity": "3", "unit": "tablespoons", "item": "butter" },
    { "quantity": "2", "unit": "slices", "item": "Cheddar cheese" }
  ],
  "instructions": ["Step 1...", "Step 2..."],
  "nutrition_estimate": {
    "calories": 440,
    "protein": "14.5g",
    "carbs": "34.5g",
    "fat": "26.5g"
  },
  "substitutions": [
    "Replace white bread with whole wheat bread for higher fiber."
  ],
  "shopping_list": {
    "dairy": ["butter", "Cheddar cheese"],
    "pantry": ["white bread"]
  },
  "related_recipes": ["Tomato Soup", "Cheesy Fries", "Coleslaw"],
  "created_at": "2026-04-15T18:20:13.122398Z"
}
```

**Error Responses:**
| Code | Reason |
|---|---|
| 422 | Invalid URL, scraping failure, non-recipe page |
| 502 | LLM API error or quota exceeded |
| 404 | Recipe ID not found |
| 500 | Unexpected server error |

---

### `GET /api/v1/recipes/`

**Response:**
```json
{
  "total": 3,
  "recipes": [
    {
      "id": 3,
      "url": "https://...",
      "title": "Grilled Cheese Sandwich",
      "cuisine": "American",
      "difficulty": "easy",
      "created_at": "2026-04-15T18:20:13Z"
    }
  ]
}
```

> Note: This lightweight response is for the history table only. Shopping list and full recipe data are returned by `GET /recipes/{id}`.

---

## Scraping Strategy

The scraper tries three strategies in order, using the first that returns ≥ 150 characters:

1. **`recipe-scrapers` (JSON-LD / Schema.org)** — reads structured `prepTime`, `cookTime`, `totalTime`, ingredients and instructions directly from the page's embedded metadata. Works on most modern recipe sites including many Cloudflare-protected ones.

2. **`cloudscraper` (Cloudflare bypass)** — emulates a real browser TLS fingerprint to pass JS challenges. Falls back to BeautifulSoup on the fetched HTML.

3. **`httpx` + BeautifulSoup** — plain async HTTP with realistic browser headers and content extraction from `<article>`, `<main>`, or recipe-class divs.

---

## Prompt Templates

All LLM prompts live in `prompts/` and can be edited without touching source code. They use Python `str.format()` placeholders.

| File | Purpose | Key variables |
|---|---|---|
| `recipe_extraction.txt` | Core extraction (title, times, ingredients, instructions) | `{recipe_text}` |
| `nutrition_estimation.txt` | Per-serving macro estimates | `{title}`, `{servings}`, `{ingredients_text}` |
| `substitutions.txt` | 3 ingredient substitution suggestions | `{title}`, `{cuisine}`, `{ingredients_text}` |
| `shopping_list.txt` | Group ingredients by category | `{ingredients_text}` |
| `related_recipes.txt` | 3 complementary dish suggestions | `{title}`, `{cuisine}`, `{difficulty}`, `{key_ingredients}` |

---

## Environment Variables

### Required for ALL deployments

| Variable | Description | Example |
|---|---|---|
| `NVIDIA_API_KEY` | **REQUIRED** — NVIDIA AI Endpoints key from [build.nvidia.com](https://build.nvidia.com/) | `nvapi-xxxx` |
| `DATABASE_URL` | **REQUIRED** — Async PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |

### Required to change in production

| Variable | Default | What to change |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Set to your actual frontend domain, e.g. `https://yourapp.com` |
| `DEBUG` | `true` | Set to `false` in production |

### Optional (have sensible defaults)

| Variable | Default | Description |
|---|---|---|
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA API endpoint |
| `LLM_MODEL_NAME` | `meta/llama-3.1-70b-instruct` | Any supported NVIDIA model |
| `LLM_TEMPERATURE` | `0.2` | Lower = more deterministic JSON extraction |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `SCRAPER_MAX_TEXT_LENGTH` | `8000` | Max chars passed to LLM context |
| `SCRAPER_REQUEST_TIMEOUT` | `30` | HTTP scrape timeout in seconds |
| `APP_TITLE` | `Recipe Extractor & Meal Planner API` | OpenAPI title |
| `APP_VERSION` | `1.0.0` | OpenAPI version |

### Docker-only (if using docker-compose local Postgres)

| Variable | Default |
|---|---|
| `POSTGRES_DB` | `recipe_db` |
| `POSTGRES_USER` | `recipe_user` |
| `POSTGRES_PASSWORD` | `recipe_pass` |
| `POSTGRES_PORT` | `5432` |

---

## Deployment Checklist

```
Backend (e.g. Render, Railway, Fly.io):
  ✅ Set NVIDIA_API_KEY
  ✅ Set DATABASE_URL (Supabase session pooler URL)
  ✅ Set CORS_ORIGINS to your frontend domain
  ✅ Set DEBUG=false
  ✅ Run: alembic upgrade head (one-time migration)
  ✅ Start: uvicorn app.main:app --host 0.0.0.0 --port 8000

Frontend (e.g. Vercel, Netlify):
  ✅ Set VITE_API_BASE_URL if not using a proxy (update recipeApi.js BASE_URL)
  ✅ Ensure build command: npm run build
  ✅ Publish directory: dist/
```

---

## Error Handling

All API errors return structured JSON:

```json
{
  "error": "ScrapingError",
  "detail": "Access denied (HTTP 403). The site is blocking automated access.",
  "status_code": 422
}
```

| Exception | HTTP Code | Trigger |
|---|---|---|
| `ScrapingError` | 422 | Bad URL, network error, bot-blocked, not a recipe page |
| `LLMError` | 502 | NVIDIA API failure, malformed JSON response |
| `RecipeNotFoundError` | 404 | ID not in database |
| `RequestValidationError` | 422 | Invalid request body |
| `Exception` (catch-all) | 500 | Unexpected server error |

---

## curl / PowerShell Testing

```bash
# Extract recipe
curl -X POST http://localhost:8000/api/v1/recipes/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/"}'

# List all saved recipes
curl http://localhost:8000/api/v1/recipes/

# Get specific recipe
curl http://localhost:8000/api/v1/recipes/1

# Health check
curl http://localhost:8000/health
```

```powershell
# PowerShell (Windows)
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/api/v1/recipes/extract" `
  -ContentType "application/json" `
  -Body '{"url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/"}'
```

---

## Stopping Services

```bash
# Stop API server: Ctrl+C

# Stop PostgreSQL (Docker — preserves data):
docker-compose stop

# Full reset (removes data):
docker-compose down -v
```
