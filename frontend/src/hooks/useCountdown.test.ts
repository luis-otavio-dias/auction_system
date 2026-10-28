import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCountdown } from './useCountdown'

const ENDS_AT = '2026-10-27T12:10:00.000Z'
const START = new Date('2026-10-27T12:00:00.000Z')

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(START)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('recalcula o offset na chegada de cada serverTime sem salto regressivo', () => {
    const { result, rerender } = renderHook(
      (props: { serverTime: string }) => useCountdown(ENDS_AT, props.serverTime),
      { initialProps: { serverTime: START.toISOString() } },
    )

    expect(result.current.seconds).toBe(600)

    act(() => {
      vi.advanceTimersByTime(30_000)
    })
    expect(result.current.seconds).toBe(570)

    rerender({ serverTime: new Date(START.getTime() + 30_000).toISOString() })
    expect(result.current.seconds).toBe(570)

    act(() => {
      vi.advanceTimersByTime(10_000)
    })
    expect(result.current.seconds).toBe(560)

    rerender({ serverTime: new Date(START.getTime() + 40_000).toISOString() })
    expect(result.current.seconds).toBe(560)

    act(() => {
      vi.advanceTimersByTime(60_000)
    })
    expect(result.current.seconds).toBe(500)
    expect(result.current.ended).toBe(false)
  })

  it('encerra quando o relógio sincronizado alcança ends_at', () => {
    const { result } = renderHook(() => useCountdown(ENDS_AT, START.toISOString()))

    act(() => {
      vi.advanceTimersByTime(600_000)
    })

    expect(result.current.seconds).toBe(0)
    expect(result.current.ended).toBe(true)
    expect(result.current.label).toBe('Encerrado')
  })
})
