import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import {
  applyTheme,
  initialTheme,
  prefersLightTheme,
  readStoredTheme,
  storeTheme,
  type Theme,
} from '../lib/theme'

/** Dark/light switch. Both themes are designed, not inverted — see index.css. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof window === 'undefined' ? 'dark' : initialTheme(readStoredTheme(), prefersLightTheme()),
  )

  useEffect(() => {
    applyTheme(theme)
    storeTheme(theme)
  }, [theme])

  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border
                 border-border text-muted transition-colors duration-150
                 hover:bg-surface-2 hover:text-foreground"
    >
      {theme === 'dark' ? <Sun size={15} aria-hidden /> : <Moon size={15} aria-hidden />}
    </button>
  )
}
