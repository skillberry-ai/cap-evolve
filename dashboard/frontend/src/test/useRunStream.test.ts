import { describe, expect, it } from 'vitest'
import { initialStreamState, streamReducer } from '../lib/useRunStream'

describe('streamReducer', () => {
  it('goes live on open', () => {
    const s = streamReducer(initialStreamState, { type: 'open' })
    expect(s.status).toBe('live')
  })

  it('appends events with an incrementing seq and derives kind', () => {
    let s = streamReducer(initialStreamState, { type: 'open' })
    s = streamReducer(s, { type: 'event', data: { kind: 'step', candidate: 'cand_0001' } })
    s = streamReducer(s, { type: 'event', data: { kind: 'evaluate', split: 'val' } })
    expect(s.count).toBe(2)
    expect(s.log.map((e) => e.kind)).toEqual(['step', 'evaluate'])
    expect(s.log.map((e) => e.seq)).toEqual([0, 1])
  })

  it('caps the log at 200 entries', () => {
    let s = streamReducer(initialStreamState, { type: 'open' })
    for (let i = 0; i < 250; i++) {
      s = streamReducer(s, { type: 'event', data: { kind: 'step' } })
    }
    expect(s.log).toHaveLength(200)
    expect(s.count).toBe(250)
    // keeps the most recent
    expect(s.log.at(-1)?.seq).toBe(249)
  })

  it('transitions to done and idle', () => {
    let s = streamReducer(initialStreamState, { type: 'done' })
    expect(s.status).toBe('done')
    s = streamReducer(initialStreamState, { type: 'idle' })
    expect(s.status).toBe('idle')
  })

  it('falls back to "event" kind when missing', () => {
    const s = streamReducer(initialStreamState, { type: 'event', data: { foo: 1 } })
    expect(s.log[0].kind).toBe('event')
  })
})
