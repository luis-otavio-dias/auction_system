import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { useAuth } from '../../context/auth-context'
import { useToast } from '../../context/toast-context'
import type { Role } from '../../types/api'
import { errorMessage } from '../../utils/errors'

export default function RegisterPage() {
  const { register } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [publicAlias, setPublicAlias] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('BIDDER')
  const [error, setError] = useState<string | null>(null)
  const [limited, setLimited] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    setLimited(false)
    try {
      await register({
        email,
        password,
        role: role === 'SELLER' ? 'SELLER' : 'BIDDER',
        public_alias: publicAlias,
      })
      showToast('Cadastro criado e sessão iniciada.', 'Bem-vindo')
      navigate('/', { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 404 || cause.status === 405)) {
        setLimited(true)
        setError('O cadastro público não está disponível neste backend. Use as credenciais do seed para entrar.')
        return
      }
      if (cause instanceof ApiError) {
        const fields = Object.values(cause.fields).flat()
        setError(fields[0] ?? (cause.detail || 'Não foi possível criar o cadastro.'))
      } else if (cause instanceof Error) {
        setError(errorMessage(cause, 'Não foi possível criar o cadastro.'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="container auth-page">
      <div className="auth-card">
        <p className="eyebrow gold">Cadastro público</p>
        <h1>Criar conta</h1>
        <p className="auth-copy">Escolha atuar como licitante ou leiloeiro. O alias é o único nome exibido publicamente.</p>
        <form onSubmit={event => { void submit(event) }}>
          <label htmlFor="register-alias">Alias público</label>
          <input id="register-alias" value={publicAlias} onChange={event => setPublicAlias(event.target.value)} maxLength={24} required />
          <label htmlFor="register-email">E-mail</label>
          <input id="register-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required />
          <label htmlFor="register-password">Senha</label>
          <input id="register-password" type="password" autoComplete="new-password" minLength={8} value={password} onChange={event => setPassword(event.target.value)} required />
          <fieldset className="role-field">
            <legend>Perfil</legend>
            <label><input type="radio" name="role" value="BIDDER" checked={role === 'BIDDER'} onChange={() => setRole('BIDDER')} /> Licitante</label>
            <label><input type="radio" name="role" value="SELLER" checked={role === 'SELLER'} onChange={() => setRole('SELLER')} /> Leiloeiro</label>
          </fieldset>
          {error && (
            <div className="bid-error" role="alert">
              <p>{error}</p>
              {limited && <p>Use <code>cliente1@demo.com</code> ou <code>leiloeiro@demo.com</code> com a senha <code>demo-password-123</code>.</p>}
            </div>
          )}
          <button className="primary-button confirm-bid" type="submit" disabled={submitting}>{submitting ? 'Criando…' : 'Criar conta'}</button>
        </form>
        <p className="auth-switch">Já tem conta? <Link to="/login">Entrar</Link></p>
      </div>
    </div>
  )
}
