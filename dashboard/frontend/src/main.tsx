import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import { STATIC_MODE, applyDataBaseOverride } from './lib/api'
import { Hub } from './routes/Hub'
import { RunDeepDive } from './routes/RunDeepDive'
import { Compare } from './routes/Compare'
import {
  applyTheme,
  initialTheme,
  prefersLightTheme,
  readStoredTheme,
} from './lib/theme'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 2000, refetchOnWindowFocus: false } },
})

// Hash routing in the static export so client-side routes resolve from any subpath
// (python -m http.server, GitHub Pages, etc.) without server rewrites. Live dashboard
// keeps clean BrowserRouter paths (the backend serves index.html for unknown routes).
const Router = STATIC_MODE ? HashRouter : BrowserRouter

applyDataBaseOverride()

// Apply the stored/OS theme BEFORE the first paint so a light-mode reader never sees a
// flash of the dark palette while React mounts.
applyTheme(initialTheme(readStoredTheme(), prefersLightTheme()))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route path="/" element={<Hub />} />
          <Route path="/runs/:id" element={<RunDeepDive />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  </StrictMode>,
)
