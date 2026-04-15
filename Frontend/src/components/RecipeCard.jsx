// src/components/RecipeCard.jsx
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import NutritionBadge from './NutritionBadge'
import IngredientList from './IngredientList'
import InstructionSteps from './InstructionSteps'
import ShoppingList from './ShoppingList'

const DIFF = {
  easy:   { variant: 'success', icon: '✅' },
  medium: { variant: 'warning', icon: '⚡' },
  hard:   { variant: 'danger',  icon: '🔥' },
}

function SectionTitle({ icon, children }) {
  return (
    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
      <span>{icon}</span>{children}
    </p>
  )
}

function TimeChip({ icon, label, value }) {
  if (!value) return null
  return (
    <div className="flex items-center gap-2 bg-muted/40 border border-border rounded-lg px-3 py-2">
      <span>{icon}</span>
      <div>
        <p className="text-[10px] text-muted-foreground leading-none mb-0.5">{label}</p>
        <p className="text-sm font-medium text-foreground leading-none">{value}</p>
      </div>
    </div>
  )
}

export default function RecipeCard({ recipe }) {
  if (!recipe) return null
  const {
    title, cuisine, difficulty, servings,
    prep_time, cook_time, total_time,
    ingredients, instructions,
    nutrition_estimate, substitutions,
    shopping_list, related_recipes,
    url, created_at,
  } = recipe

  const diff = DIFF[difficulty?.toLowerCase()] || DIFF.medium
  const date = created_at ? new Date(created_at).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' }) : null

  return (
    <div className="space-y-4 animate-slide-up">

      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="text-xl font-bold text-foreground leading-tight flex-1">{title || 'Untitled Recipe'}</h2>
            <div className="flex flex-wrap gap-2">
              {cuisine && <Badge variant="secondary">🌍 {cuisine}</Badge>}
              {difficulty && <Badge variant={diff.variant}>{diff.icon} {difficulty}</Badge>}
            </div>
          </div>

          <div className="flex flex-wrap gap-2.5 mt-2">
            <TimeChip icon="⏱️" label="Prep"     value={prep_time}  />
            <TimeChip icon="🍳" label="Cook"     value={cook_time}  />
            <TimeChip icon="⏰" label="Total"    value={total_time} />
            {servings && <TimeChip icon="🍽️" label="Servings" value={servings} />}
          </div>
        </CardHeader>
      </Card>

      {/* Nutrition */}
      {nutrition_estimate && (
        <Card>
          <CardContent className="pt-6">
            <SectionTitle icon="📊">Nutrition <span className="font-normal text-muted-foreground/60 normal-case tracking-normal">per serving</span></SectionTitle>
            <NutritionBadge nutrition={nutrition_estimate} />
          </CardContent>
        </Card>
      )}

      {/* Ingredients + Instructions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {ingredients?.length > 0 && (
          <Card>
            <CardContent className="pt-6">
              <SectionTitle icon="🧂">Ingredients ({ingredients.length})</SectionTitle>
              <IngredientList ingredients={ingredients} />
            </CardContent>
          </Card>
        )}
        {instructions?.length > 0 && (
          <Card>
            <CardContent className="pt-6">
              <SectionTitle icon="📋">Instructions</SectionTitle>
              <InstructionSteps instructions={instructions} />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Shopping List */}
      {shopping_list && Object.keys(shopping_list).length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <SectionTitle icon="🛒">Shopping List</SectionTitle>
            <ShoppingList shoppingList={shopping_list} />
          </CardContent>
        </Card>
      )}

      {/* Substitutions */}
      {substitutions?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <SectionTitle icon="💡">Substitutions</SectionTitle>
            <ul className="space-y-2.5">
              {substitutions.map((sub, i) => (
                <li key={i} className="flex gap-3 text-sm text-foreground/80 leading-relaxed">
                  <span className="text-amber-400 mt-0.5 flex-shrink-0 font-bold">•</span>
                  {sub}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Related Recipes */}
      {related_recipes?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <SectionTitle icon="🔗">You Might Also Like</SectionTitle>
            <div className="flex flex-wrap gap-2">
              {related_recipes.map((r, i) => (
                <Badge key={i} variant="secondary" className="text-sm py-1 px-3">🍴 {r}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Footer */}
      {(url || date) && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-1 pb-1 text-xs text-muted-foreground/50">
          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer"
               className="hover:text-primary transition-colors truncate max-w-xs">
              🔗 {url}
            </a>
          )}
          {date && <span>Extracted {date}</span>}
        </div>
      )}
    </div>
  )
}
