import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { GitCompareArrows, LayoutGrid } from 'lucide-react'
import { Capybara } from './Capybara'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/', label: 'Runs', Icon: LayoutGrid },
  { to: '/compare', label: 'Compare', Icon: GitCompareArrows },
]

/** Adaptive chrome: sidebar on ≥lg, top bar on small screens. */
export function AppShell({ children, live = false }: { children: ReactNode; live?: boolean }) {
  const { pathname } = useLocation()
  const isActive = (to: string) => (to === '/' ? pathname === '/' : pathname.startsWith(to))

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[220px_1fr]">
      {/* Sidebar (lg+) */}
      <aside className="hidden lg:flex flex-col gap-1 border-r border-border bg-surface px-3 py-4">
        <Link to="/" className="mb-4 flex items-center gap-2 px-2">
          <Capybara size={30} state={live ? 'live' : 'idle'} />
          <span className="text-lg font-semibold tracking-tight">
            cap<span className="text-accent">·</span>evolve
          </span>
        </Link>
        {NAV.map(({ to, label, Icon }) => (
          <Link
            key={to}
            to={to}
            aria-current={isActive(to) ? 'page' : undefined}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-200',
              isActive(to)
                ? 'bg-surface-2 text-foreground'
                : 'text-muted hover:text-foreground hover:bg-surface-2/60',
            )}
          >
            <Icon size={16} aria-hidden />
            {label}
          </Link>
        ))}
        <div className="mt-auto px-2 text-[11px] text-muted">watch capability evolve</div>
      </aside>

      {/* Top bar (mobile) */}
      <header className="lg:hidden sticky top-0 z-20 flex items-center gap-2 border-b border-border bg-surface/90 px-4 py-3 backdrop-blur">
        <Capybara size={26} state={live ? 'live' : 'idle'} />
        <span className="font-semibold tracking-tight">
          cap<span className="text-accent">·</span>evolve
        </span>
        <nav className="ml-auto flex gap-1">
          {NAV.map(({ to, label, Icon }) => (
            <Link
              key={to}
              to={to}
              aria-current={isActive(to) ? 'page' : undefined}
              aria-label={label}
              className={cn(
                'flex h-11 w-11 items-center justify-center rounded-lg',
                isActive(to) ? 'bg-surface-2 text-foreground' : 'text-muted',
              )}
            >
              <Icon size={18} aria-hidden />
            </Link>
          ))}
        </nav>
      </header>

      <main className="min-w-0 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  )
}
