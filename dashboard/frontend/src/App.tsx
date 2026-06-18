import { Capybara } from './components/Capybara'

/**
 * Task 1 placeholder shell — proves theme, fonts, and brand render.
 * Routing (Hub, RunDeepDive) is introduced in Task 3.
 */
function App() {
  return (
    <div className="min-h-dvh flex flex-col items-center justify-center gap-6 px-6 text-center">
      <Capybara size={72} state="live" />
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          cap<span className="text-accent">·</span>evolve
        </h1>
        <p className="mt-2 text-muted">watch capability evolve</p>
      </div>
      <p className="tnum text-sm text-muted">
        baseline <span className="text-foreground">0.00</span> →{' '}
        best <span className="text-accent">1.00</span>
        <span className="text-accepted"> (+100%)</span>
      </p>
    </div>
  )
}

export default App
