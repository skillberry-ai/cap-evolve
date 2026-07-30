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

describe('streamReducer: stall/crash status frames (#118)', () => {
  it('promotes a stalled verdict and keeps its reason', () => {
    let s = streamReducer(initialStreamState, { type: 'open' })
    s = streamReducer(s, {
      type: 'status',
      data: { status: 'stalled', detail: 'STALLED — no events for 42.0m, over this run’s own threshold 12.0m' },
    })
    expect(s.status).toBe('stalled')
    expect(s.detail).toContain('STALLED')
  })

  it('promotes a crashed verdict', () => {
    const s = streamReducer(initialStreamState, {
      type: 'status',
      data: { status: 'crashed', detail: 'CRASHED — the process that owned this run is gone' },
    })
    expect(s.status).toBe('crashed')
  })

  it('a live verdict does NOT downgrade a finished run', () => {
    let s = streamReducer(initialStreamState, { type: 'done' })
    s = streamReducer(s, { type: 'status', data: { status: 'live', detail: 'working' } })
    expect(s.status).toBe('done')
  })

  it('a stalled verdict does NOT downgrade a finished run either', () => {
    let s = streamReducer(initialStreamState, { type: 'done' })
    s = streamReducer(s, { type: 'status', data: { status: 'stalled', detail: 'STALLED' } })
    expect(s.status).toBe('done')
  })

  it('a slow-but-healthy run stays live and clears a stale reason', () => {
    let s = streamReducer(initialStreamState, { type: 'open' })
    s = streamReducer(s, { type: 'status', data: { status: 'stalled', detail: 'STALLED' } })
    expect(s.status).toBe('stalled')
    // progress resumes: the next event re-arms 'live' and drops the stale reason
    s = streamReducer(s, { type: 'event', data: { kind: 'step' } })
    expect(s.status).toBe('live')
    expect(s.detail).toBeNull()
    s = streamReducer(s, { type: 'status', data: { status: 'live', detail: 'working — last event 3s ago' } })
    expect(s.status).toBe('live')
  })
})
