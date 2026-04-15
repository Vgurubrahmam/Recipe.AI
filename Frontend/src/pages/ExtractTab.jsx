// src/pages/ExtractTab.jsx
import { useState } from 'react'
import { extractRecipe } from '@/api/recipeApi'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Loader2, Link, ClipboardPaste, RotateCcw, Sparkles, AlertTriangle } from 'lucide-react'
import RecipeCard from '@/components/RecipeCard'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function ExtractTab() {
  const [url, setUrl]         = useState('')
  const [loading, setLoading] = useState(false)
  const [recipe, setRecipe]   = useState(null)
  const [error, setError]     = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!url.trim()) return
    setLoading(true); setError(null); setRecipe(null)
    try {
      setRecipe(await extractRecipe(url.trim()))
    } catch (err) {
      setError(err.message || 'Extraction failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handlePaste() {
    try { setUrl(await navigator.clipboard.readText()) } catch {}
  }

  function handleReset() { setUrl(''); setRecipe(null); setError(null) }

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
              <CardDescription>Paste any recipe blog URL to extract structured data with AI</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex gap-2">
              <Input
                id="recipe-url-input"
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://www.allrecipes.com/recipe/..."
                disabled={loading}
                className="flex-1 h-11 text-base"
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

            <div className="flex gap-2">
              <Button
                id="extract-btn"
                type="submit"
                disabled={loading || !url.trim()}
                className="flex-1"
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Extracting…</>
                ) : (
                  <><Sparkles className="w-4 h-4" /> Extract Recipe</>
                )}
              </Button>
              {(recipe || error) && (
                <Button id="reset-btn" type="button" variant="outline" onClick={handleReset}>
                  <RotateCcw className="w-4 h-4" /> Reset
                </Button>
              )}
            </div>

            {!recipe && !loading && !error && (
              <p className="text-xs text-muted-foreground pt-1">
                Works with: allrecipes.com · food.com · simplyrecipes.com · cookieandkate.com
              </p>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Loading skeleton */}
      {loading && <LoadingSpinner />}

      {/* Error */}
      {error && !loading && (
        <Alert variant="destructive" className="animate-fade-in">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Extraction Failed</AlertTitle>
          <AlertDescription className="mt-1 leading-relaxed">{error}</AlertDescription>
        </Alert>
      )}

      {/* Result */}
      {recipe && !loading && <RecipeCard recipe={recipe} />}
    </div>
  )
}
