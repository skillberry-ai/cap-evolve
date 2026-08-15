/** Theme resolution + application, shared by main.tsx (pre-paint) and ThemeToggle. */

export const THEME_KEY = 'capevolve-theme'
export type Theme = 'dark' | 'light'

/** Stored choice, else the OS preference. Dark is the design's default. */
export function initialTheme(stored: string | null, prefersLight: boolean): Theme {
  if (stored === 'light' || stored === 'dark') return stored
  return prefersLight ? 'light' : 'dark'
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('light', theme === 'light')
}

/** Storage can be absent, blocked (private mode), or stubbed (jsdom) — none of which
 *  is a reason for the theme to throw. */
export function readStoredTheme(): string | null {
  try {
    return window.localStorage?.getItem?.(THEME_KEY) ?? null
  } catch {
    return null
  }
}

export function storeTheme(theme: Theme): void {
  try {
    window.localStorage?.setItem?.(THEME_KEY, theme)
  } catch {
    /* private mode — the choice just won't persist */
  }
}

export function prefersLightTheme(): boolean {
  try {
    return window.matchMedia?.('(prefers-color-scheme: light)').matches ?? false
  } catch {
    return false
  }
}
