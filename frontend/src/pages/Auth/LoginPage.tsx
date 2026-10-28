import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { useAuth } from '../../context/auth-context'
import { useToast } from '../../context/toast-context'
import { errorMessage } from '../../utils/errors'

export default function LoginPage() {
  const { login } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const next = params.get('next') ?? '/'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
      showToast('Sessão iniciada com cookies HttpOnly.', 'Bem-vindo')
      navigate(next, { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(cause.status === 401 ? 'E-mail ou senha inválidos.' : cause.detail || 'Não foi possível entrar.')
      } else if (cause instanceof Error) {
        setError(errorMessage(cause, 'Não foi possível entrar.'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const fillDemo = (role: 'bidder' | 'seller') => {
    setEmail(role === 'seller' ? 'leiloeiro@demo.com' : 'cliente1@demo.com')
    setPassword('demo-password-123')
    setError(null)
  }

  return (
    <div className="container auth-page">
      <div className="auth-card">
        <p className="eyebrow gold">Acesso</p>
        <h1>Entrar na conta</h1>
        <p className="auth-copy">A sessão usa cookies HttpOnly. O frontend nunca lê nem armazena access ou refresh tokens.</p>
        <form onSubmit={event => { void submit(event) }}>
          <label htmlFor="login-email">E-mail</label>
          <input id="login-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required />
          <label htmlFor="login-password">Senha</label>
          <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required />
          {error && <p className="bid-error" role="alert">{error}</p>}
          <button className="primary-button confirm-bid" type="submit" disabled={submitting}>{submitting ? 'Entrando…' : 'Entrar'}</button>
        </form>
        <div className="demo-box">
          <p className="eyebrow">Credenciais do seed</p>
          <p>Senha padrão: <code>demo-password-123</code></p>
          <div className="demo-actions">
            <button type="button" className="quick-bid" onClick={() => fillDemo('bidder')}>Usar cliente1</button>
            <button type="button" className="quick-bid" onClick={() => fillDemo('seller')}>Usar leiloeiro</button>
          </div>
        </div>
        <p className="auth-switch">Ainda não tem conta? <Link to="/cadastro">Criar cadastro</Link></p>
      </div>
    </div>
  )
}
