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

const EXAMPLE_URLS = [
  { site: 'AllRecipes', url: 'https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/' },
  { site: 'Food.com', url: 'https://www.food.com/recipe/grilled-cheese-sandwich-14609' },
  { site: 'SimplyRecipes', url: 'https://www.simplyrecipes.com/recipes/homemade_pizza/' },
]

export default function ExtractTab() {
  const [url, setUrl]           = useState('')
  const [loading, setLoading]   = useState(false)
  const [recipe, setRecipe]     = useState(null)
  const [error, setError]       = useState(null)
  const [urlWarning, setUrlWarning] = useState(null)

  function handleUrlChange(e) {
    const val = e.target.value
    setUrl(val)
    if (val && isNonRecipeUrl(val)) {
      setUrlWarning('This looks like a gallery or listing page — please use a single recipe URL (e.g. /recipe/12345/name/).')
    } else {
      setUrlWarning(null)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true); setError(null); setRecipe(null)
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
      setUrlWarning(isNonRecipeUrl(text) ? 'This looks like a gallery or listing page — please use a single recipe URL.' : null)
    } catch {}
  }

  function handleReset() { setUrl(''); setRecipe(null); setError(null); setUrlWarning(null) }

  function useExample(exUrl) {
    setUrl(exUrl)
    setUrlWarning(null)
    setError(null)
    setRecipe(null)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">

      {/* Input Card */}
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
                placeholder="https://www.allrecipes.com/recipe/12345/recipe-name/"
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

            {/* URL warning */}
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

          {/* Example URLs */}
          {!recipe && !loading && !error && (
            <div className="pt-1">
              <p className="text-xs text-muted-foreground mb-2">Try an example:</p>
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
            </div>
          )}
        </CardContent>
      </Card>

      {/* Loading skeleton */}
      {loading && <LoadingSpinner />}

      {/* Error */}
      {error && !loading && (
        <Alert variant="destructive" className="animate-fade-in">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Extraction Failed</AlertTitle>
          <AlertDescription className="mt-1 leading-relaxed space-y-2">
            <p>{error}</p>
            {(error.toLowerCase().includes('gallery') || error.toLowerCase().includes('strategy') || error.toLowerCase().includes('403') || error.toLowerCase().includes('402')) && (
              <p className="text-xs opacity-80">
                💡 Make sure you're using a <strong>single recipe page</strong> URL (look for <code>/recipe/</code> in the URL), not a gallery, category, or search page.
              </p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Result */}
      {recipe && !loading && <RecipeCard recipe={recipe} />}
    </div>
  )
}
