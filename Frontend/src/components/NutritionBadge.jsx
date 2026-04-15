// src/components/NutritionBadge.jsx
import { Card, CardContent } from '@/components/ui/card'

const NUTRIENTS = [
  { key:'calories', label:'Calories', icon:'🔥', unit:'kcal', cls:'from-orange-500/20 to-orange-600/10 border-orange-500/20 text-orange-400' },
  { key:'protein',  label:'Protein',  icon:'💪', unit:'',     cls:'from-blue-500/20 to-blue-600/10 border-blue-500/20 text-blue-400' },
  { key:'carbs',    label:'Carbs',    icon:'🌾', unit:'',     cls:'from-amber-500/20 to-amber-600/10 border-amber-500/20 text-amber-400' },
  { key:'fat',      label:'Fat',      icon:'🥑', unit:'',     cls:'from-purple-500/20 to-purple-600/10 border-purple-500/20 text-purple-400' },
]

export default function NutritionBadge({ nutrition }) {
  if (!nutrition) return null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {NUTRIENTS.map(({ key, label, icon, unit, cls }) => {
        const val = nutrition[key]
        if (val == null) return null
        return (
          <div key={key}
               className={`bg-gradient-to-br ${cls} border rounded-xl p-3 text-center transition-transform hover:scale-105`}>
            <div className="text-2xl mb-1">{icon}</div>
            <div className="text-lg font-bold text-foreground">
              {val}{unit && <span className="text-xs ml-0.5 font-normal">{unit}</span>}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
          </div>
        )
      })}
    </div>
  )
}
