import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

export interface TabDef {
  id: string
  label: string
  disabled?: boolean
  badge?: string
}

/**
 * Lightweight accessible tabs with an animated active underline.
 *
 * Controlled when `value` + `onChange` are passed (RunDeepDive drives them from the URL
 * so a tab is deep-linkable and the browser back button works), uncontrolled otherwise.
 *
 * Keyboard contract (WAI-ARIA tabs pattern — required for the #139 cross-links to be
 * reachable without a mouse): a single tab stop for the whole tablist (roving tabindex),
 * then Left/Right/Home/End to move between tabs. Enter/Space are native `<button>`
 * activation and need no handler. Disabled tabs are skipped. Selection is never conveyed
 * by colour alone — the active tab is also bold and carries aria-selected.
 */
export function Tabs({
  tabs,
  initial,
  value,
  onChange,
  children,
}: {
  tabs: TabDef[]
  initial?: string
  value?: string
  onChange?: (id: string) => void
  children: (active: string) => ReactNode
}) {
  const firstEnabled = tabs.find((t) => !t.disabled)?.id ?? tabs[0]?.id
  const [internal, setInternal] = useState(initial ?? firstEnabled)
  // An unknown `value` (e.g. a stale ?tab= in a shared URL) falls back to the first tab
  // rather than rendering an empty panel.
  const active =
    value == null ? internal : tabs.some((t) => t.id === value) ? value : firstEnabled
  const select = (id: string) => (onChange ? onChange(id) : setInternal(id))

  // Unique per instance so nested Tabs don't share a framer layoutId (two underlines
  // fighting over one animated element) or duplicate DOM ids.
  const uid = useId()
  const listRef = useRef<HTMLDivElement>(null)

  const onKeyDown = (e: KeyboardEvent) => {
    const enabled = tabs.filter((t) => !t.disabled)
    if (!enabled.length) return
    const delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    let next: string | undefined
    if (delta !== 0) {
      const i = enabled.findIndex((t) => t.id === active)
      next = enabled[(i + delta + enabled.length) % enabled.length].id
    } else if (e.key === 'Home') next = enabled[0].id
    else if (e.key === 'End') next = enabled[enabled.length - 1].id
    if (!next) return
    e.preventDefault()
    select(next)
    // Move focus with selection: an automatic-activation tablist keeps focus and
    // selection on the same tab.
    listRef.current?.querySelector<HTMLElement>(`[data-tab-id="${next}"]`)?.focus()
  }

  return (
    <div>
      <div
        ref={listRef}
        role="tablist"
        onKeyDown={onKeyDown}
        className="flex flex-wrap gap-1 border-b border-border"
      >
        {tabs.map((t) => {
          const isActive = t.id === active
          return (
            <button
              key={t.id}
              data-tab-id={t.id}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`${uid}-panel`}
              tabIndex={isActive ? 0 : -1}
              disabled={t.disabled}
              onClick={() => !t.disabled && select(t.id)}
              className={cn(
                'relative px-3 py-2 text-sm transition-colors duration-150',
                t.disabled
                  ? 'cursor-not-allowed text-muted/40'
                  : isActive
                    ? 'font-semibold text-foreground'
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
                  layoutId={`tab-underline-${uid}`}
                  className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary"
                />
              )}
            </button>
          )
        })}
      </div>
      {/* tabIndex=-1: not a tab stop, but a programmatic focus target — closing an overlay
          whose opener has unmounted hands focus here instead of dropping it to <body>. */}
      <div id={`${uid}-panel`} role="tabpanel" tabIndex={-1} className="pt-4">
        {children(active)}
      </div>
    </div>
  )
}
