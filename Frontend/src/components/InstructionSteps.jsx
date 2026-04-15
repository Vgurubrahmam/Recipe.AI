// src/components/InstructionSteps.jsx

export default function InstructionSteps({ instructions }) {
  if (!instructions?.length) return null
  return (
    <ol className="space-y-3">
      {instructions.map((step, i) => (
        <li key={i} className="flex gap-3 group">
          <span className="mt-0.5 flex-shrink-0 w-6 h-6 rounded-full bg-primary/15 border border-primary/30
                           text-primary text-xs font-bold flex items-center justify-center
                           group-hover:bg-primary/25 transition-colors">
            {i + 1}
          </span>
          <p className="text-sm text-foreground/80 leading-relaxed pt-0.5">{step}</p>
        </li>
      ))}
    </ol>
  )
}
