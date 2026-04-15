// src/App.jsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import ExtractTab from './pages/ExtractTab'
import HistoryTab from './pages/HistoryTab'
import { Sparkles, BookOpen, Cpu } from 'lucide-react'
import { useState } from 'react'

export default function App() {
  const [tab, setTab] = useState('extract')

  return (
    <div className="min-h-screen flex flex-col bg-background">

      {/* ── Header ─────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center">
              <span className="text-xl">🍽️</span>
            </div>
            <div className="leading-tight">
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest">AI-Powered</p>
              <h1 className="text-sm font-bold text-foreground leading-none">
                Recipe<span className="text-primary">.</span>AI
              </h1>
            </div>
          </div>

          {/* Tabs nav */}
          <Tabs value={tab} onValueChange={setTab} className="w-auto">
            <TabsList>
              <TabsTrigger value="extract" id="tab-extract" className="gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Extract Recipe</span>
                <span className="sm:hidden">Extract</span>
              </TabsTrigger>
              <TabsTrigger value="history" id="tab-history" className="gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Saved Recipes</span>
                <span className="sm:hidden">Saved</span>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* Status */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="hidden sm:flex items-center gap-1">
              <Cpu className="w-3 h-3" /> API Live
            </span>
          </div>
        </div>
      </header>

      {/* ── Content ────────────────────────────────── */}
      <main className="flex-1">
        {tab === 'extract' && <ExtractTab />}
        {tab === 'history' && <HistoryTab onGoExtract={() => setTab('extract')} />}
      </main>

      {/* ── Footer ─────────────────────────────────── */}
      <footer className="border-t border-border py-4">
        <p className="text-center text-xs text-muted-foreground/50">
          Recipe Extractor &amp; Meal Planner · Powered by NVIDIA Llama 3.1 · FastAPI Backend
        </p>
      </footer>
    </div>
  )
}
