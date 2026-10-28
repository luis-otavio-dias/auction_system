import type { ReactNode } from 'react'

export function LoadingState({ label = 'Carregando…' }: { label?: string }) {
  return <div className="state-block" role="status"><span className="spinner" aria-hidden="true" /><p>{label}</p></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-block state-error" role="alert">
      <p>{message}</p>
      {onRetry && <button className="text-link" onClick={onRetry}>Tentar novamente <span aria-hidden="true">→</span></button>}
    </div>
  )
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p className="eyebrow gold">Catálogo</p>
      <h2>{title}</h2>
      <p>{text}</p>
      {action}
    </div>
  )
}
