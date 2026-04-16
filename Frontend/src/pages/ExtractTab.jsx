// src/pages/ExtractTab.jsx
import { useState } from 'react'
import { extractRecipe } from '@/api/recipeApi'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Loader2, Link, ClipboardPaste, RotateCcw, Sparkles, AlertTriangle, Info } from 'lucide-react'
import RecipeCard from '@/components/RecipeCard'
import LoadingSpinner from '@/components/LoadingSpinner'

// URL patterns that are listing/gallery pages, not single recipes
const NON_RECIPE_PATTERNS = [
  /\/gallery\//i,
  /\/recipes\/$/i,
  /\/recipes\?/i,
  /\/topic\//i,
  /\/category\//i,
  /\/collection\//i,
  /\/search\//i,
  /\/tag\//i,
]

function isNonRecipeUrl(url) {
  try {
    const u = new URL(url)
    return NON_RECIPE_PATTERNS.some(p => p.test(u.pathname + u.search))
  } catch {
    return false
  }
}

/**
 * AllRecipes article-style URLs (missing /recipe/ in path) return HTTP 402
 * to all automated scrapers, including headless browsers.
 */
function isAllRecipesArticleUrl(url) {
  try {
    const u = new URL(url)
    return u.hostname.includes('allrecipes.com') && !u.pathname.startsWith('/recipe/')
  } catch {
    return false
  }
}

const EXAMPLE_URLS = [
  { site: 'Food.com',      url: 'https://www.food.com/recipe/grilled-cheese-sandwich-14609' },
  { site: 'SimplyRecipes', url: 'https://www.simplyrecipes.com/recipes/homemade_pizza/' },
  { site: 'Tasty',         url: 'https://tasty.co/recipe/the-best-chocolate-chip-cookies' },
  { site: 'SeriousEats',   url: 'https://www.seriouseats.com/the-best-chocolate-chip-cookies-recipe-chocolate' },
  { site: 'AllRecipes ✓',  url: 'https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/' },
]

export default function ExtractTab() {
  const [url, setUrl]           = useState('')
  const [loading, setLoading]   = useState(false)
  const [recipe, setRecipe]     = useState(null)
  const [error, setError]       = useState(null)
  const [urlWarning, setUrlWarning] = useState(null)
  const [showDetails, setShowDetails] = useState(false)

  function handleUrlChange(e) {
    const val = e.target.value
    setUrl(val)
    if (val && isNonRecipeUrl(val)) {
      setUrlWarning('This looks like a gallery or listing page — please use a single recipe URL (e.g. /recipe/12345/name/).')
    } else if (val && isAllRecipesArticleUrl(val)) {
      setUrlWarning('AllRecipes article-style URLs (without /recipe/ in the path) are heavily bot-protected and may fail. Try the classic /recipe/… format.')
    } else {
      setUrlWarning(null)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true); setError(null); setRecipe(null); setShowDetails(false)
    try {
      setRecipe(await extractRecipe(url.trim()))
    } catch (err) {
      setError(err.message || 'Extraction failed. Please try a direct recipe page URL.')
    } finally {
      setLoading(false)
    }
  }

  async function handlePaste() {
    try {
      const text = await navigator.clipboard.readText()
      setUrl(text)
      if (isNonRecipeUrl(text)) {
        setUrlWarning('This looks like a gallery or listing page — please use a single recipe URL.')
      } else if (isAllRecipesArticleUrl(text)) {
        setUrlWarning('AllRecipes article-style URLs may be bot-protected. Try a /recipe/… URL instead.')
      } else {
        setUrlWarning(null)
      }
    } catch {}
  }

  function handleReset() {
    setUrl(''); setRecipe(null); setError(null); setUrlWarning(null); setShowDetails(false)
  }

  function useExample(exUrl) {
    setUrl(exUrl); setUrlWarning(null); setError(null); setRecipe(null); setShowDetails(false)
  }

  // ── Parse error for display ──────────────────────────────────
  const isBlockError = error && (
    error.includes('402') || error.includes('403') ||
    error.includes('strategy') || error.includes('scraping') ||
    error.includes('bot') || error.includes('paywall')
  )

  // Bullet-point failure lines (for collapsible technical details)
  const errorBullets = error
    ? error.split('\n').filter(l => l.trim().startsWith('•') || l.trim().startsWith('–'))
    : []

  // Show only the first line as the human-readable summary
  const errorSummary = error ? error.split('\n')[0] : ''

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">

      {/* ── Input Card ─────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Link className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle>Extract Recipe</CardTitle>
              <CardDescription>
                Paste a <strong className="text-foreground">single recipe page</strong> URL — not a gallery or search page
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex gap-2">
              <Input
                id="recipe-url-input"
                type="url"
                value={url}
                onChange={handleUrlChange}
                placeholder="https://www.food.com/recipe/12345/recipe-name"
                disabled={loading}
                className={`flex-1 h-11 text-base ${urlWarning ? 'border-amber-500/60 focus-visible:ring-amber-500/30' : ''}`}
                autoFocus
              />
              <Button
                id="paste-url-btn"
                type="button"
                variant="outline"
                size="icon"
                onClick={handlePaste}
                disabled={loading}
                title="Paste from clipboard"
                className="h-11 w-11 flex-shrink-0"
              >
                <ClipboardPaste className="w-4 h-4" />
              </Button>
            </div>

            {urlWarning && (
              <div className="flex items-start gap-2 text-xs text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                <span>{urlWarning}</span>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                id="extract-btn"
                type="submit"
                disabled={loading || !url.trim()}
                className="flex-1"
              >
                {loading
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Extracting…</>
                  : <><Sparkles className="w-4 h-4" /> Extract Recipe</>
                }
              </Button>
              {(recipe || error) && (
                <Button id="reset-btn" type="button" variant="outline" onClick={handleReset}>
                  <RotateCcw className="w-4 h-4" /> Reset
                </Button>
              )}
            </div>
          </form>

          {/* Example URL chips (only when idle) */}
          {!recipe && !loading && !error && (
            <div className="pt-1 space-y-2">
              <p className="text-xs text-muted-foreground">Try a reliable example:</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_URLS.map(({ site, url: exUrl }) => (
                  <button
                    key={site}
                    type="button"
                    onClick={() => useExample(exUrl)}
                    className="text-xs px-2.5 py-1 rounded-md bg-muted hover:bg-primary/10 hover:text-primary border border-border transition-colors"
                  >
                    {site}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground/60">
                ⚠️ AllRecipes article-style URLs may block automated scrapers — prefer food.com, simplyrecipes.com, or tasty.co
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Loading skeleton ────────────────────────────────── */}
      {loading && <LoadingSpinner />}

      {/* ── Error card ──────────────────────────────────────── */}
      {error && !loading && (
        <Alert variant="destructive" className="animate-fade-in">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Extraction Failed</AlertTitle>
          <AlertDescription className="mt-1 space-y-3">

            {/* Plain-English first line */}
            <p className="leading-relaxed">{errorSummary}</p>

            {/* AllRecipes article URL — targeted explanation */}
            {isAllRecipesArticleUrl(url) && (
              <div className="text-xs bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2 space-y-1">
                <p className="font-semibold">⚠️ AllRecipes article-style URL detected</p>
                <p className="opacity-80">
                  This URL uses AllRecipes' newer article format (no <code>/recipe/</code> in the path),
                  which returns <strong>HTTP 402</strong> to all automated scrapers — including headless browsers.
                  Use the classic format instead:
                </p>
                <p className="font-mono opacity-70 text-[11px] break-all">
                  https://www.allrecipes.com/recipe/&lt;id&gt;/&lt;recipe-name&gt;/
                </p>
              </div>
            )}

            {/* Generic bot-block hint */}
            {isBlockError && !isAllRecipesArticleUrl(url) && (
              <p className="text-xs opacity-80">
                💡 This site&apos;s bot-protection blocked all scraping attempts. Try one of the working examples below.
              </p>
            )}

            {/* Collapsible technical strategy details */}
            {errorBullets.length > 0 && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowDetails(d => !d)}
                  className="text-xs underline underline-offset-2 opacity-70 hover:opacity-100 transition-opacity"
                >
                  {showDetails ? 'Hide' : 'Show'} technical details
                </button>
                {showDetails && (
                  <ul className="mt-2 space-y-1">
                    {errorBullets.map((line, i) => (
                      <li key={i} className="text-[11px] font-mono opacity-70 leading-snug">{line.trim()}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* Working-example chips inline in error */}
            <div className="space-y-1.5">
              <p className="text-xs font-medium opacity-80">Try a working URL instead:</p>
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLE_URLS.map(({ site, url: exUrl }) => (
                  <button
                    key={site}
                    type="button"
                    onClick={() => { useExample(exUrl); setError(null) }}
                    className="text-xs px-2.5 py-1 rounded-md bg-background/30 hover:bg-background/50 border border-destructive/30 hover:border-destructive/60 transition-colors"
                  >
                    {site}
                  </button>
                ))}
              </div>
            </div>

          </AlertDescription>
        </Alert>
      )}

      {/* ── Recipe result ───────────────────────────────────── */}
      {recipe && !loading && <RecipeCard recipe={recipe} />}
    </div>
  )
}
