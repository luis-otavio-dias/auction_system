import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, isAbortError, websocketUrl } from '../api/client'
import { fetchWsTicket } from '../api/auth'
import { decodeLotEvent } from '../api/decoders'
import { firstString } from '../api/json'
import { getLot, listBids, placeBid } from '../api/lots'
import type { JsonValue } from '../api/json'
import { useAuth } from '../context/auth-context'
import { evaluateEvent, evaluateSnapshot, mergeLotEvent, mergeLotSnapshot } from '../domain/lotState'
import { bidErrorMessage, GENERIC_BID_ERROR } from '../domain/bidErrors'
import type { BidHistoryEntry, ConnectionState, LotDetail, LotSnapshot } from '../types/api'
import { errorMessage } from '../utils/errors'
import { parseAmount } from '../utils/format'
import { createClientId } from '../utils/id'

const POLL_INTERVAL_MS = 4000
const CONNECTION_MAX_AGE_MS = 14 * 60 * 1000
const MAX_RECONNECT_DELAY_MS = 30000

interface PendingBid {
  id: string
  amount: string
}

export interface BidSubmitOutcome {
  ok: boolean
  code: string
  message: string
  stateVersion: number | null
  available: string | null
  minimumBid: string | null
}

export interface LotRoomController {
  lot: LotDetail | null
  bids: BidHistoryEntry[]
  bidsCount: number
  hasMoreBids: boolean
  loading: boolean
  submitting: boolean
  error: string | null
  historyError: string | null
  connection: ConnectionState
  reload: () => Promise<void>
  loadMoreBids: () => Promise<void>
  submitBid: (amount: string) => Promise<BidSubmitOutcome>
}

export function useLotRoom(lotId: string): LotRoomController {
  const { user } = useAuth()
  const [lot, setLot] = useState<LotDetail | null>(null)
  const [bids, setBids] = useState<BidHistoryEntry[]>([])
  const [bidsCount, setBidsCount] = useState(0)
  const [hasMoreBids, setHasMoreBids] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('offline')
  const versionRef = useRef(0)
  const lotRef = useRef<LotDetail | null>(null)
  const bidsCountRef = useRef(0)
  const bidsRequestRef = useRef(0)
  const nextPageRef = useRef(2)
  const pendingBidRef = useRef<PendingBid | null>(null)
  const loadingMoreRef = useRef(false)

  const refreshBids = useCallback(async (signal?: AbortSignal) => {
    const request = bidsRequestRef.current + 1
    bidsRequestRef.current = request
    try {
      const page = await listBids(lotId, 1, signal)
      if (request !== bidsRequestRef.current) {
        return
      }
      setBids([...page.results].sort((first, second) => second.sequence - first.sequence))
      bidsCountRef.current = page.count
      setBidsCount(page.count)
      setHasMoreBids(page.next !== null)
      nextPageRef.current = 2
      setHistoryError(null)
    } catch (cause) {
      if (cause instanceof Error && isAbortError(cause)) {
        return
      }
      if (request === bidsRequestRef.current && cause instanceof Error) {
        setHistoryError(errorMessage(cause, 'Não foi possível carregar o histórico.'))
      }
    }
  }, [lotId])

  const applySnapshot = useCallback((detail: LotDetail, force = false) => {
    const decision = evaluateSnapshot(versionRef.current, detail.state_version)
    const sameVersion = detail.state_version === versionRef.current
    if (!decision.accept && !(force && sameVersion)) {
      return false
    }
    versionRef.current = detail.state_version
    lotRef.current = detail
    setLot(detail)
    setError(null)
    if (detail.bids_count !== bidsCountRef.current) {
      void refreshBids()
    }
    return true
  }, [refreshBids])

  const fetchSnapshot = useCallback(async (signal?: AbortSignal, force = false) => {
    try {
      const detail = await getLot(lotId, signal)
      applySnapshot(detail, force)
    } catch (cause) {
      if (cause instanceof Error && isAbortError(cause)) {
        return
      }
      if (cause instanceof Error) {
        setError(errorMessage(cause, 'Não foi possível atualizar o lote.'))
      }
    }
  }, [lotId, applySnapshot])

  const applyStreamSnapshot = useCallback((snapshot: LotSnapshot) => {
    const current = lotRef.current
    if (current === null) {
      void fetchSnapshot()
      return
    }
    if (snapshot.state_version < versionRef.current) {
      return
    }
    if (versionRef.current > 0 && snapshot.state_version > versionRef.current + 1) {
      void fetchSnapshot()
      return
    }
    const merged = mergeLotSnapshot(current, snapshot)
    versionRef.current = snapshot.state_version
    lotRef.current = merged
    setLot(merged)
    setError(null)
    if (snapshot.bids_count !== bidsCountRef.current) {
      void refreshBids()
    }
  }, [fetchSnapshot, refreshBids])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let ageTimer: number | null = null
    let attempt = 0

    const clearReconnect = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (ageTimer !== null) {
        window.clearTimeout(ageTimer)
        ageTimer = null
      }
    }

    const scheduleReconnect = () => {
      if (!active) {
        return
      }
      const delay = Math.min(MAX_RECONNECT_DELAY_MS, 1000 * 2 ** attempt)
      attempt += 1
      reconnectTimer = window.setTimeout(() => {
        void connect()
      }, delay)
    }

    const handleMessage = (data: string) => {
      let parsed: JsonValue
      try {
        parsed = JSON.parse(data) as JsonValue
      } catch {
        return
      }
      const event = decodeLotEvent(parsed)
      if (event === null) {
        return
      }
      if (event.type === 'lot.snapshot') {
        applyStreamSnapshot(event.snapshot)
        return
      }
      const decision = evaluateEvent(versionRef.current, event.state_version)
      if (decision.stale) {
        return
      }
      if (!decision.accept) {
        if (decision.gap) {
          void fetchSnapshot()
        }
        return
      }
      versionRef.current = event.state_version
      const current = lotRef.current
      if (current === null) {
        void fetchSnapshot()
        return
      }
      const merged = mergeLotEvent(current, event)
      lotRef.current = merged
      setLot(merged)
      if (event.type === 'bid.accepted') {
        void refreshBids()
      }
      if (event.type === 'lot.closed' || event.type === 'lot.cancelled') {
        void fetchSnapshot()
      }
    }

    const connect = async () => {
      if (!active) {
        return
      }
      setConnection('connecting')
      let ticket: string | null = null
      if (user !== null) {
        try {
          ticket = (await fetchWsTicket()).ticket
        } catch {
          ticket = null
        }
      }
      if (!active) {
        return
      }
      let nextSocket: WebSocket
      try {
        nextSocket = new WebSocket(websocketUrl(`/ws/lots/${lotId}/`, ticket))
      } catch {
        setConnection('offline')
        scheduleReconnect()
        return
      }
      socket = nextSocket
      nextSocket.onopen = () => {
        attempt = 0
        setConnection('open')
        ageTimer = window.setTimeout(() => {
          nextSocket.close(1000, 'renovar conexão')
        }, CONNECTION_MAX_AGE_MS)
      }
      nextSocket.onmessage = event => {
        if (typeof event.data === 'string') {
          handleMessage(event.data)
        }
      }
      nextSocket.onerror = () => {
        nextSocket.close()
      }
      nextSocket.onclose = () => {
        if (ageTimer !== null) {
          window.clearTimeout(ageTimer)
          ageTimer = null
        }
        if (socket === nextSocket) {
          socket = null
        }
        if (active) {
          setConnection('offline')
          scheduleReconnect()
        }
      }
    }

    const load = async () => {
      try {
        const detail = await getLot(lotId, controller.signal)
        if (!active) {
          return
        }
        applySnapshot(detail)
        await refreshBids(controller.signal)
      } catch (cause) {
        if (cause instanceof Error && isAbortError(cause)) {
          return
        }
        if (active && cause instanceof Error) {
          setError(errorMessage(cause, 'Não foi possível carregar o lote.'))
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()
    void connect()

    const pollTimer = window.setInterval(() => {
      if (document.hidden) {
        return
      }
      void fetchSnapshot(controller.signal)
    }, POLL_INTERVAL_MS)

    return () => {
      active = false
      window.clearInterval(pollTimer)
      clearReconnect()
      controller.abort()
      const closing = socket
      socket = null
      if (closing !== null) {
        closing.onclose = null
        closing.close(1000, 'sala encerrada')
      }
      setConnection('offline')
    }
  }, [lotId, user, applySnapshot, applyStreamSnapshot, fetchSnapshot, refreshBids])

  const reload = useCallback(async () => {
    await fetchSnapshot()
    await refreshBids()
  }, [fetchSnapshot, refreshBids])

  const loadMoreBids = useCallback(async () => {
    if (!hasMoreBids || loadingMoreRef.current) {
      return
    }
    loadingMoreRef.current = true
    const pageNumber = nextPageRef.current
    try {
      const page = await listBids(lotId, pageNumber)
      const ordered = [...page.results].sort((first, second) => second.sequence - first.sequence)
      setBids(current => [...current, ...ordered])
      bidsCountRef.current = page.count
      setBidsCount(page.count)
      setHasMoreBids(page.next !== null)
      nextPageRef.current = pageNumber + 1
      setHistoryError(null)
    } catch (cause) {
      if (cause instanceof Error) {
        setHistoryError(errorMessage(cause, 'Não foi possível carregar mais lances.'))
      }
    } finally {
      loadingMoreRef.current = false
    }
  }, [hasMoreBids, lotId])

  const submitBid = useCallback(async (amount: string): Promise<BidSubmitOutcome> => {
    const current = lotRef.current
    if (current === null) {
      return {
        ok: false,
        code: 'LOT_UNAVAILABLE',
        message: GENERIC_BID_ERROR,
        stateVersion: null,
        available: null,
        minimumBid: null,
      }
    }
    const parsed = parseAmount(amount)
    if (parsed === null || parsed <= 0) {
      return {
        ok: false,
        code: 'INVALID_AMOUNT',
        message: 'Informe um valor de lance válido.',
        stateVersion: null,
        available: null,
        minimumBid: null,
      }
    }
    const normalized = parsed.toFixed(2)
    let pending = pendingBidRef.current
    if (pending === null || pending.amount !== normalized) {
      pending = { id: createClientId(), amount: normalized }
      pendingBidRef.current = pending
    }
    setSubmitting(true)
    try {
      const result = await placeBid(lotId, normalized, pending.id)
      pendingBidRef.current = null
      if (result.lot !== null) {
        applySnapshot(result.lot, true)
      }
      await fetchSnapshot(undefined, true)
      await refreshBids()
      return {
        ok: true,
        code: '',
        message: result.detail ?? 'Lance registrado com sucesso.',
        stateVersion: result.state_version,
        available: null,
        minimumBid: null,
      }
    } catch (cause) {
      if (cause instanceof ApiError) {
        if (cause.status !== 0 && cause.status < 500) {
          pendingBidRef.current = null
        }
        return {
          ok: false,
          code: cause.code,
          message: bidErrorMessage(cause.code, cause.detail),
          stateVersion: null,
          available: firstString(cause.context, ['available']),
          minimumBid: firstString(cause.context, ['minimum_bid']),
        }
      }
      return {
        ok: false,
        code: 'UNKNOWN',
        message: cause instanceof Error ? errorMessage(cause, GENERIC_BID_ERROR) : GENERIC_BID_ERROR,
        stateVersion: null,
        available: null,
        minimumBid: null,
      }
    } finally {
      setSubmitting(false)
    }
  }, [lotId, applySnapshot, fetchSnapshot, refreshBids])

  return {
    lot,
    bids,
    bidsCount,
    hasMoreBids,
    loading,
    submitting,
    error,
    historyError,
    connection,
    reload,
    loadMoreBids,
    submitBid,
  }
}
