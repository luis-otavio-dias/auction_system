import { createContext, useContext } from 'react'
import type { AppNotification, ConnectionState } from '../types/api'

export interface NotificationsContextValue {
  notifications: AppNotification[]
  unread: number
  connection: ConnectionState
  markAllRead: () => void
  clear: () => void
}

export const NotificationsContext = createContext<NotificationsContextValue | null>(null)

export function useNotifications(): NotificationsContextValue {
  const context = useContext(NotificationsContext)
  if (context === null) {
    throw new Error('useNotifications precisa estar dentro de NotificationsProvider.')
  }
  return context
}
