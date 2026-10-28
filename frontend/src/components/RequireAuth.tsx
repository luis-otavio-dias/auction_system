import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/auth-context'
import type { Role } from '../types/api'
import { LoadingState } from './ui/States'

export default function RequireAuth({ roles, children }: { roles?: readonly Role[]; children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <div className="container page-section"><LoadingState label="Verificando sua sessão…" /></div>
  }
  if (user === null) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="container page-section">
        <div className="empty-state">
          <p className="eyebrow gold">Acesso restrito</p>
          <h2>Esta área é exclusiva para {roles.includes('SELLER') ? 'leiloeiros' : 'licitantes'}.</h2>
          <p>Seu perfil atual não tem permissão para acessar esta página.</p>
          <Link className="text-link" to="/">Voltar para a vitrine <span aria-hidden="true">→</span></Link>
        </div>
      </div>
    )
  }
  return <>{children}</>
}
