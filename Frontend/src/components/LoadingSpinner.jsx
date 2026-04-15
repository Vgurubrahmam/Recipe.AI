// src/components/LoadingSpinner.jsx
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

export default function LoadingSpinner() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4 animate-fade-in">
      {/* Header skeleton */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between gap-4">
            <Skeleton className="h-7 w-2/3" />
            <div className="flex gap-2">
              <Skeleton className="h-6 w-20 rounded-full" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
          </div>
          <div className="flex gap-3 mt-4 flex-wrap">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-14 w-28 rounded-xl" />)}
          </div>
        </CardHeader>
      </Card>

      {/* Nutrition skeleton */}
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-4 w-28 mb-4" />
          <div className="grid grid-cols-4 gap-3">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
          </div>
        </CardContent>
      </Card>

      {/* 2-col skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="pt-6 space-y-3">
            <Skeleton className="h-4 w-28 mb-2" />
            {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-5 w-full" />)}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 space-y-3">
            <Skeleton className="h-4 w-28 mb-2" />
            {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-5 w-full" />)}
          </CardContent>
        </Card>
      </div>

      {/* Bottom status */}
      <div className="flex items-center justify-center gap-3 py-4">
        <div className="w-5 h-5 border-2 border-muted border-t-primary rounded-full animate-spin" />
        <p className="text-sm text-muted-foreground">
          Extracting recipe with AI… <span className="text-primary">~20–40s</span>
        </p>
      </div>
    </div>
  )
}
