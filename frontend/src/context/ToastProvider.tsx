import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import Toast from '../components/Toast'
import { ToastContext } from './toast-context'
import type { ToastContextValue } from './toast-context'

interface ToastState {
  message: string
  title: string
}

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null)

  useEffect(() => {
    if (toast === null) {
      return
    }
    const timer = window.setTimeout(() => setToast(null), 5000)
    return () => window.clearTimeout(timer)
  }, [toast])

  const value = useMemo<ToastContextValue>(() => ({
    showToast: (message: string, title = 'Aviso') => setToast({ message, title }),
  }), [])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast && <Toast message={toast.message} title={toast.title} onDismiss={() => setToast(null)} />}
    </ToastContext.Provider>
  )
}
