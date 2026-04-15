// src/components/IngredientList.jsx
import { Separator } from '@/components/ui/separator'

export default function IngredientList({ ingredients }) {
  if (!ingredients?.length) return null
  return (
    <ul className="space-y-0">
      {ingredients.map((ing, i) => {
        const parts = [ing.quantity, ing.unit, ing.item].filter(Boolean)
        return (
          <li key={i}>
            <div className="flex items-center gap-3 py-2.5 group">
              <span className="flex-shrink-0 w-5 h-5 rounded-md border border-primary/30 bg-primary/10
                               flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                <span className="w-2 h-2 rounded-sm bg-primary/70" />
              </span>
              <span className="text-sm text-foreground/80 capitalize leading-snug">{parts.join(' ')}</span>
            </div>
            {i < ingredients.length - 1 && <Separator className="opacity-30" />}
          </li>
        )
      })}
    </ul>
  )
}
