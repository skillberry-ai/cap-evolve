/** Live run feed over SSE (/api/runs/{id}/stream).
 *
 * Rendering data stays authoritative in the TanStack Query cache; this hook
 * supplies the live *event ticker* + connection status, and calls `onActivity`
 * on each event so the caller can refetch the reduced run. The reducer is pure
 * and exported for unit testing.
 */
import { useEffect, useReducer, useRef } from 'react'
import { api, STATIC_MODE } from './api'

export type StreamStatus = 'connecting' | 'live' | 'done' | 'idle' | 'error'

export interface StreamEntry {
  kind: string
  data: Record<string, unknown>
  seq: number
}

export interface StreamState {
  status: StreamStatus
  log: StreamEntry[]
  count: number
}

export type StreamAction =
  | { type: 'open' }
  | { type: 'event'; data: Record<string, unknown> }
  | { type: 'done' }
  | { type: 'idle' }
  | { type: 'error' }

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
      return { status: 'live', log, count: state.count + 1 }
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
  // Keep the latest callback in a ref WITHOUT writing during render (that is a real
  // React violation: a render must be side-effect free). The EventSource effect below
  // only ever reads activityRef.current, so a one-tick-late write is harmless.
  const activityRef = useRef(onActivity)
  useEffect(() => {
    activityRef.current = onActivity
  }, [onActivity])

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
    es.onerror = () => dispatch({ type: 'error' })

    return () => es.close()
  }, [id])

  return state
}
