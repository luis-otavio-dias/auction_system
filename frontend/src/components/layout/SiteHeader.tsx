import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import type { Role } from '../../types/api'
import { useAuth } from '../../context/auth-context'
import Icon from '../Icon'
import NotificationBell from './NotificationBell'

const roleLabels: Record<Role, string> = {
  BIDDER: 'Licitante',
  SELLER: 'Leiloeiro',
}

export default function SiteHeader() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)
  const handleLogout = async () => {
    await logout()
    closeMenu()
    navigate('/')
  }
  const seller = user?.role === 'SELLER'
  return (
    <header className="header">
      <div className="container header-inner">
        <Link className="brand" to="/" aria-label="Leilões — início" onClick={closeMenu}>Leilões</Link>
        <nav className={menuOpen ? 'navigation is-open' : 'navigation'} aria-label="Navegação principal">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''} onClick={closeMenu}>Leilões</NavLink>
          <NavLink to="/carteira" className={({ isActive }) => isActive ? 'active' : ''} onClick={closeMenu}>Carteira</NavLink>
          <NavLink to="/meus-arremates" className={({ isActive }) => isActive ? 'active' : ''} onClick={closeMenu}>Meus arremates</NavLink>
          {seller && <NavLink to="/painel" className={({ isActive }) => isActive ? 'active' : ''} onClick={closeMenu}>Painel do leiloeiro</NavLink>}
          {user === null && <NavLink to="/cadastro" className={({ isActive }) => isActive ? 'active' : ''} onClick={closeMenu}>Criar conta</NavLink>}
        </nav>
        <div className="header-actions">
          <Link className="search-toggle" to="/#catalogo" onClick={closeMenu}><Icon name="search" /><span>Buscar</span></Link>
          <NotificationBell />
          {user === null
            ? <Link className="login-link" to="/login">Entrar</Link>
            : (
              <div className="profile">
                <div>
                  <span>{roleLabels[user.role]}</span>
                  <p>{user.public_alias || user.email}</p>
                </div>
                <button className="icon-button logout-button" aria-label="Sair da conta" onClick={() => { void handleLogout() }}>
                  <Icon name="logout" />
                </button>
              </div>
            )}
          <button className="icon-button menu-toggle" aria-label="Abrir navegação" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
            <Icon name={menuOpen ? 'close' : 'menu'} />
          </button>
        </div>
      </div>
    </header>
  )
}
