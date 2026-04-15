// src/components/RecipeModal.jsx
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogDescription,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import RecipeCard from './RecipeCard'

export default function RecipeModal({ recipe, open, onOpenChange }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b border-border">
          <div className="flex items-start gap-3 pr-6">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Recipe Details</p>
              <DialogTitle className="text-base font-semibold truncate">
                {recipe?.title || 'Loading…'}
              </DialogTitle>
            </div>
            {recipe?.difficulty && (
              <Badge variant={
                recipe.difficulty === 'easy' ? 'success' :
                recipe.difficulty === 'hard' ? 'danger' : 'warning'
              } className="flex-shrink-0">
                {recipe.difficulty}
              </Badge>
            )}
          </div>
          <DialogDescription className="sr-only">Full recipe details</DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[calc(90vh-80px)]">
          <div className="p-6">
            <RecipeCard recipe={recipe} />
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
