import { describe, expect, it } from 'vitest'
import { compactNum, deltaTone, duration, pct, signedPct, usd } from '../lib/format'

describe('pct', () => {
  it('formats a 0..1 reward as a percentage', () => {
    expect(pct(0.752)).toBe('75.2%')
    expect(pct(1)).toBe('100.0%')
    expect(pct(0, 0)).toBe('0%')
  })
  it('returns a dash for null/NaN', () => {
    expect(pct(null)).toBe('—')
    expect(pct(undefined)).toBe('—')
    expect(pct(NaN)).toBe('—')
  })
})

describe('signedPct', () => {
  it('prefixes a sign', () => {
    expect(signedPct(12.34)).toBe('+12.3%')
    expect(signedPct(-4)).toBe('-4.0%')
    expect(signedPct(0)).toBe('0.0%')
  })
})

describe('usd', () => {
  it('uses 3 digits under $1, else 2', () => {
    expect(usd(0.0123)).toBe('$0.012')
    expect(usd(12.5)).toBe('$12.50')
    expect(usd(null)).toBe('—')
  })
})

describe('compactNum', () => {
  it('compacts large numbers', () => {
    expect(compactNum(1500)).toBe('1.5K')
    expect(compactNum(2_300_000)).toBe('2.3M')
    expect(compactNum(42)).toBe('42')
  })
})

describe('duration', () => {
  it('renders short human durations', () => {
    expect(duration(45)).toBe('45s')
    expect(duration(75)).toBe('1m 15s')
    expect(duration(3661)).toBe('1h 1m')
    expect(duration(null)).toBe('—')
  })
})

describe('deltaTone', () => {
  it('classifies sign', () => {
    expect(deltaTone(3)).toBe('up')
    expect(deltaTone(-1)).toBe('down')
    expect(deltaTone(0)).toBe('flat')
    expect(deltaTone(null)).toBe('flat')
  })
})
