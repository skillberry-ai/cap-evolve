/** Live run feed over SSE (/api/runs/{id}/stream).
 *
 * Rendering data stays authoritative in the TanStack Query cache; this hook
 * supplies the live *event ticker* + connection status, and calls `onActivity`
 * on each event so the caller can refetch the reduced run. The reducer is pure
 * and exported for unit testing.
 */
import { useEffect, useReducer, useRef } from 'react'
import { api, STATIC_MODE } from './api'

export type StreamStatus = 'connecting' | 'live' | 'done' | 'idle' | 'error' | 'stalled' | 'crashed'

export interface StreamEntry {
  kind: string
  data: Record<string, unknown>
  seq: number
}

export interface StreamState {
  status: StreamStatus
  log: StreamEntry[]
  count: number
  /** Why, with the numbers, from the backend's `status` frame — the same sentence
   * `cap-evolve tail` prints for the same run dir (#118). */
  detail?: string | null
}

export type StreamAction =
  | { type: 'open' }
  | { type: 'event'; data: Record<string, unknown> }
  | { type: 'done' }
  | { type: 'idle' }
  | { type: 'error' }
  | { type: 'status'; data: Record<string, unknown> }

const LOG_CAP = 200

export const initialStreamState: StreamState = { status: 'connecting', log: [], count: 0 }

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case 'open':
      return { ...state, status: 'live' }
    case 'event': {
      const entry: StreamEntry = {
        kind: String(action.data.kind ?? 'event'),
        data: action.data,
        seq: state.count,
      }
      const log = [...state.log, entry].slice(-LOG_CAP)
      return { status: 'live', log, count: state.count + 1, detail: null }
    }
    case 'status': {
      // The backend's periodic verdict. `live` here means "quiet but within this run's
      // own demonstrated pace" — it must not overwrite a terminal 'done'.
      if (state.status === 'done') return state
      const s = String(action.data.status ?? 'live')
      const status: StreamStatus =
        s === 'stalled' || s === 'crashed' ? s : state.status === 'connecting' ? 'live' : state.status
      return { ...state, status, detail: (action.data.detail as string | null) ?? null }
    }
    case 'done':
      return { ...state, status: 'done' }
    case 'idle':
      return { ...state, status: 'idle' }
    case 'error':
      return { ...state, status: 'error' }
    default:
      return state
  }
}

export function useRunStream(id: string | undefined, onActivity?: () => void): StreamState {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState)
  const activityRef = useRef(onActivity)
  activityRef.current = onActivity

  useEffect(() => {
    // Static export has no backend / SSE: the run is finished, so report 'done'.
    if (STATIC_MODE) {
      dispatch({ type: 'done' })
      return
    }
    if (!id || typeof EventSource === 'undefined') return
    const es = new EventSource(api.streamURL(id))

    es.addEventListener('open', () => dispatch({ type: 'open' }))
    es.addEventListener('snapshot', () => dispatch({ type: 'open' }))
    es.addEventListener('event', (e) => {
      try {
        dispatch({ type: 'event', data: JSON.parse((e as MessageEvent).data) })
        activityRef.current?.()
      } catch {
        /* ignore malformed frame */
      }
    })
    es.addEventListener('done', () => {
      dispatch({ type: 'done' })
      es.close()
    })
    es.addEventListener('idle', () => {
      dispatch({ type: 'idle' })
      es.close()
    })
    // #118: the backend now names which kind of quiet a silent run is, instead of
    // closing the connection with an ambiguous idle frame that read like completion.
    es.addEventListener('status', (e) => {
      try {
        dispatch({ type: 'status', data: JSON.parse((e as MessageEvent).data) })
      } catch {
        /* ignore malformed frame */
      }
    })
    es.onerror = () => dispatch({ type: 'error' })

    return () => es.close()
  }, [id])

  return state
}
