// src/components/ShoppingList.jsx
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

const ICONS = { dairy:'🥛', bakery:'🥖', produce:'🥦', pantry:'🥫', meat:'🥩', seafood:'🐟', frozen:'🧊', beverages:'🧃', spices:'🌶️', other:'🛒' }
const icon = (cat) => ICONS[cat.toLowerCase()] || ICONS.other

export default function ShoppingList({ shoppingList }) {
  if (!shoppingList || !Object.keys(shoppingList).length) return null
  const entries = Object.entries(shoppingList)
  return (
    <div className="space-y-3">
      {entries.map(([cat, items], idx) => (
        <div key={cat}>
          <div className="flex items-center gap-2 mb-2">
            <span>{icon(cat)}</span>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{cat}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {items.map((item, i) => (
              <Badge key={i} variant="muted" className="capitalize">{item}</Badge>
            ))}
          </div>
          {idx < entries.length - 1 && <Separator className="mt-3 opacity-30" />}
        </div>
      ))}
    </div>
  )
}
