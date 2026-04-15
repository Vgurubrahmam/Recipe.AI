// src/pages/HistoryTab.jsx
import { useState, useEffect, useCallback } from 'react'
import { listRecipes, getRecipeById } from '@/api/recipeApi'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import {
  Table, TableBody, TableCell,
  TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { RefreshCw, ShoppingCart, Sparkles, AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import RecipeModal from '@/components/RecipeModal'
import ShoppingList from '@/components/ShoppingList'

const DIFF = { easy:'success', medium:'warning', hard:'danger' }

function fmt(iso) {
  return new Date(iso).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' })
}

function TableSkeleton() {
  return Array.from({ length: 4 }).map((_, i) => (
    <TableRow key={i}>
      <TableCell><Skeleton className="h-4 w-4 rounded" /></TableCell>
      <TableCell><Skeleton className="h-4 w-4" /></TableCell>
      <TableCell><Skeleton className="h-4 w-48" /></TableCell>
      <TableCell className="hidden sm:table-cell"><Skeleton className="h-4 w-20" /></TableCell>
      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
      <TableCell className="hidden lg:table-cell"><Skeleton className="h-4 w-24" /></TableCell>
      <TableCell><Skeleton className="h-8 w-16 rounded-md ml-auto" /></TableCell>
    </TableRow>
  ))
}

export default function HistoryTab({ onGoExtract }) {
  const [recipes, setRecipes]       = useState([])
  const [total, setTotal]           = useState(0)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [modalOpen, setModalOpen]   = useState(false)
  const [modalRecipe, setModalRecipe] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [selected, setSelected]     = useState(new Set())
  const [mergedList, setMergedList] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await listRecipes()
      setRecipes(d.recipes || [])
      setTotal(d.total || 0)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  async function openModal(id) {
    setModalLoading(true); setModalOpen(true)
    try { setModalRecipe(await getRecipeById(id)) }
    catch (e) { setModalOpen(false); alert('Could not load: ' + e.message) }
    finally { setModalLoading(false) }
  }

  function toggle(id) {
    setSelected(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n })
    setMergedList(null)
  }

  function toggleAll() {
    setSelected(selected.size === recipes.length ? new Set() : new Set(recipes.map(r => r.id)))
    setMergedList(null)
  }

  const [listGenerating, setListGenerating] = useState(false)

  async function generateList() {
    setListGenerating(true)
    setMergedList(null)
    try {
      // Fetch full recipe detail for each selected recipe (list items don't have shopping_list)
      const fullRecipes = await Promise.all(
        [...selected].map(id => getRecipeById(id))
      )
      const merged = {}
      fullRecipes.forEach(r => {
        if (!r.shopping_list) return
        Object.entries(r.shopping_list).forEach(([cat, items]) => {
          if (!merged[cat]) merged[cat] = new Set()
          items.forEach(i => merged[cat].add(i))
        })
      })
      const result = Object.fromEntries(
        Object.entries(merged).map(([k, v]) => [k, [...v]])
      )
      setMergedList(Object.keys(result).length ? result : {})
    } catch (e) {
      alert('Failed to generate shopping list: ' + e.message)
    } finally {
      setListGenerating(false)
    }
  }


  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Recipe History</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {loading ? 'Loading…' : `${total} recipe${total !== 1 ? 's' : ''} saved`}
          </p>
        </div>
        <Button id="refresh-history-btn" variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Failed to load history</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Table Card */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={!loading && recipes.length > 0 && selected.size === recipes.length}
                  onCheckedChange={toggleAll}
                  disabled={loading || !recipes.length}
                  aria-label="Select all"
                />
              </TableHead>
              <TableHead className="w-10">#</TableHead>
              <TableHead>Title</TableHead>
              <TableHead className="hidden sm:table-cell">Cuisine</TableHead>
              <TableHead className="hidden md:table-cell">Difficulty</TableHead>
              <TableHead className="hidden lg:table-cell">Extracted</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableSkeleton />}
            {!loading && recipes.length === 0 && !error && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-16">
                  <div className="flex flex-col items-center gap-3 text-muted-foreground">
                    <Inbox className="w-10 h-10 opacity-40" />
                    <p className="text-sm">No recipes saved yet.</p>
                    <Button variant="outline" size="sm" onClick={onGoExtract}>
                      <Sparkles className="w-4 h-4" /> Extract your first recipe
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}
            {!loading && recipes.map((r, idx) => (
              <TableRow
                key={r.id}
                data-state={selected.has(r.id) ? 'selected' : undefined}
              >
                <TableCell>
                  <Checkbox
                    checked={selected.has(r.id)}
                    onCheckedChange={() => toggle(r.id)}
                    aria-label={`Select ${r.title}`}
                  />
                </TableCell>
                <TableCell className="text-muted-foreground font-mono text-xs">{idx + 1}</TableCell>
                <TableCell className="font-medium text-foreground max-w-[180px] truncate">
                  {r.title || '—'}
                </TableCell>
                <TableCell className="hidden sm:table-cell text-muted-foreground text-xs">
                  {r.cuisine || '—'}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {r.difficulty
                    ? <Badge variant={DIFF[r.difficulty] || 'secondary'}>{r.difficulty}</Badge>
                    : <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-muted-foreground text-xs">
                  {r.created_at ? fmt(r.created_at) : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    id={`view-recipe-${r.id}`}
                    variant="ghost"
                    size="sm"
                    onClick={() => openModal(r.id)}
                    disabled={modalLoading}
                    className="text-primary hover:text-primary hover:bg-primary/10"
                  >
                    {modalLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'View →'}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Meal Planner */}
      {!loading && recipes.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShoppingCart className="w-4 h-4 text-primary" /> Meal Planner
                </CardTitle>
                <CardDescription className="mt-1">
                  {selected.size === 0
                    ? 'Select recipes above to generate a combined shopping list'
                    : `${selected.size} recipe${selected.size !== 1 ? 's' : ''} selected`}
                </CardDescription>
              </div>
              <Button
                id="generate-shopping-list-btn"
                onClick={generateList}
                disabled={selected.size === 0 || listGenerating}
              >
                {listGenerating
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
                  : <><ShoppingCart className="w-4 h-4" /> Generate Shopping List</>
                }
              </Button>
            </div>
          </CardHeader>

          {mergedList !== null && (
            <CardContent className="border-t border-border pt-4">
              {Object.keys(mergedList).length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  Shopping list data not available for selected recipes. View individual recipes for details.
                </p>
              ) : (
                <ShoppingList shoppingList={mergedList} />
              )}
            </CardContent>
          )}
        </Card>
      )}

      {/* Modal */}
      <RecipeModal
        recipe={modalLoading ? null : modalRecipe}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  )
}
