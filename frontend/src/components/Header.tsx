import { useState } from 'react'
import type { AuctionTab } from '../types/auction'
import type { InfoPanel } from '../types/ui'
import Icon from './Icon'

export default function Header({ tab, searchOpen, onToggleSearch, onInfo, onService, onSelectTab }: {
  tab: AuctionTab
  searchOpen: boolean
  onToggleSearch: () => void
  onInfo: (panel: InfoPanel) => void
  onService: (title: string) => void
  onSelectTab: (tab: AuctionTab) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const selectTab = (next: AuctionTab) => { onSelectTab(next); setMenuOpen(false) }
  const showService = (title: string) => { onService(title); setMenuOpen(false) }
  return <header className="header"><div className="container header-inner">
      <a className="brand" href="#" aria-label="Leilões — início">Leilões</a>
      <nav className={menuOpen ? 'navigation is-open' : 'navigation'} aria-label="Navegação principal">
        <a href="#catalogo" className={tab !== 'results' ? 'active' : ''} onClick={() => selectTab('live')}>Leilões</a>
        <button onClick={() => showService('Consignações')}>Consignações</button><button onClick={() => showService('Avaliações')}>Avaliações</button>
        <a href="#catalogo" className={tab === 'results' ? 'active' : ''} onClick={() => selectTab('results')}>Resultados</a><button onClick={() => showService('Minha conta')}>Minha conta</button>
      </nav>
      <div className="header-actions"><button className="search-toggle" onClick={onToggleSearch} aria-expanded={searchOpen} aria-controls="catalog-search"><Icon name="search" /><span>Buscar</span></button>
        <button className="icon-button notifications" aria-label="Notificações de lote" onClick={() => onInfo({ title: 'Notificações de lote', text: 'Nenhuma notificação disponível.' })}><Icon name="bell" /></button>
        <div className="profile"><div><span>Conta</span><p>—</p></div><span className="avatar-placeholder" aria-label="Sem foto de perfil" role="img" /></div>
        <button className="icon-button menu-toggle" aria-label="Abrir navegação" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
      </div>
    </div></header>
}
