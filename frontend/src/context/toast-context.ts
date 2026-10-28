import { createContext, useContext } from 'react'

export interface ToastContextValue {
  showToast: (message: string, title?: string) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (context === null) {
    throw new Error('useToast precisa estar dentro de ToastProvider.')
  }
  return context
}
