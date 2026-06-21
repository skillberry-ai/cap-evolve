import { useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

export interface TabDef {
  id: string
  label: string
  disabled?: boolean
  badge?: string
}

/** Lightweight accessible tabs with an animated active underline. */
export function Tabs({
  tabs,
  initial,
  children,
}: {
  tabs: TabDef[]
  initial?: string
  children: (active: string) => ReactNode
}) {
  const firstEnabled = tabs.find((t) => !t.disabled)?.id ?? tabs[0]?.id
  const [active, setActive] = useState(initial ?? firstEnabled)

  return (
    <div>
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-border">
        {tabs.map((t) => {
          const isActive = t.id === active
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={isActive}
              disabled={t.disabled}
              onClick={() => !t.disabled && setActive(t.id)}
              className={cn(
                'relative px-3 py-2 text-sm transition-colors duration-150',
                t.disabled
                  ? 'cursor-not-allowed text-muted/40'
                  : isActive
                    ? 'text-foreground'
                    : 'text-muted hover:text-foreground',
              )}
            >
              {t.label}
              {t.badge && (
                <span className="ml-1.5 rounded bg-surface-2 px-1 py-0.5 text-[10px] text-muted">
                  {t.badge}
                </span>
              )}
              {isActive && (
                <motion.span
                  layoutId="tab-underline"
                  className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary"
                />
              )}
            </button>
          )
        })}
      </div>
      <div className="pt-4">{children(active)}</div>
    </div>
  )
}
