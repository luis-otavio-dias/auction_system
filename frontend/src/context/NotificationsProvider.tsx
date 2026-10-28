import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { fetchWsTicket } from '../api/auth'
import { websocketUrl } from '../api/client'
import { decodeNotification } from '../api/decoders'
import type { JsonValue } from '../api/json'
import { useAuth } from './auth-context'
import { NotificationsContext } from './notifications-context'
import type { NotificationsContextValue } from './notifications-context'
import type { AppNotification, ConnectionState, User } from '../types/api'

const MAX_NOTIFICATIONS = 25
const CONNECTION_MAX_AGE_MS = 14 * 60 * 1000

export default function NotificationsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return (
    <NotificationsSession key={user?.id ?? 'anonymous'} user={user}>
      {children}
    </NotificationsSession>
  )
}

function NotificationsSession({ user, children }: { user: User | null; children: ReactNode }) {
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [connection, setConnection] = useState<ConnectionState>('offline')

  useEffect(() => {
    if (user === null) {
      return
    }
    let active = true
    let attempt = 0
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let ageTimer: number | null = null

    const clearTimers = () => {
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
      const delay = Math.min(30000, 1000 * 2 ** attempt)
      attempt += 1
      reconnectTimer = window.setTimeout(() => {
        void connect()
      }, delay)
    }

    const handleMessage = (data: string) => {
      try {
        const parsed = JSON.parse(data) as JsonValue
        const notification = decodeNotification(parsed)
        if (notification === null) {
          return
        }
        setNotifications(current => {
          if (current.some(item => item.id === notification.id)) {
            return current
          }
          return [notification, ...current].slice(0, MAX_NOTIFICATIONS)
        })
        setUnread(current => current + 1)
      } catch {
        return
      }
    }

    const connect = async () => {
      if (!active) {
        return
      }
      setConnection('connecting')
      let ticket: string | null
      try {
        const response = await fetchWsTicket()
        ticket = response.ticket
      } catch {
        ticket = null
      }
      if (!active) {
        return
      }
      if (ticket === null) {
        setConnection('offline')
        scheduleReconnect()
        return
      }
      const nextSocket = new WebSocket(websocketUrl('/ws/notifications/', ticket))
      socket = nextSocket
      nextSocket.onopen = () => {
        attempt = 0
        setConnection('open')
        ageTimer = window.setTimeout(() => {
          nextSocket.close(1000, 'renovar autenticação')
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

    void connect()

    return () => {
      active = false
      clearTimers()
      const closing = socket
      socket = null
      if (closing !== null) {
        closing.onclose = null
        closing.close(1000, 'encerrado')
      }
      setConnection('offline')
    }
  }, [user])

  const markAllRead = useCallback(() => setUnread(0), [])
  const clear = useCallback(() => {
    setNotifications([])
    setUnread(0)
  }, [])

  const value = useMemo<NotificationsContextValue>(() => ({
    notifications,
    unread,
    connection,
    markAllRead,
    clear,
  }), [notifications, unread, connection, markAllRead, clear])

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}
