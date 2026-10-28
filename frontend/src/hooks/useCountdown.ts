import { useEffect, useMemo, useState } from 'react'
import { clock } from '../utils/format'

export interface Countdown {
  seconds: number
  label: string
  ended: boolean
}

const readLocalClock = (): number => Date.now()

export function useCountdown(endsAt: string | null, serverTime: string | null): Countdown {
  const [now, setNow] = useState(() => Date.now())
  const offset = useMemo(() => {
    if (serverTime === null) {
      return 0
    }
    const parsed = Date.parse(serverTime)
    return Number.isNaN(parsed) ? 0 : readLocalClock() - parsed
  }, [serverTime])
  useEffect(() => {
    if (endsAt === null) {
      return
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [endsAt])
  return useMemo(() => {
    if (endsAt === null) {
      return { seconds: 0, label: '—', ended: true }
    }
    const end = Date.parse(endsAt)
    if (Number.isNaN(end)) {
      return { seconds: 0, label: '—', ended: true }
    }
    const seconds = Math.max(0, Math.floor((end - (now - offset)) / 1000))
    return {
      seconds,
      label: seconds > 0 ? clock(seconds) : 'Encerrado',
      ended: seconds <= 0,
    }
  }, [endsAt, now, offset])
}
