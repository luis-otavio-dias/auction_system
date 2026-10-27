import { useState } from 'react'
import Announcement from '../../components/Announcement'
import BidModal from '../../components/BidModal'
import Header from '../../components/Header'
import Icon from '../../components/Icon'
import LotCard from '../../components/LotCard'
import Modal from '../../components/Modal'
import Toast from '../../components/Toast'
import { useAuction } from '../../hooks/useAuction'
import { useElapsedTime } from '../../hooks/useElapsedTime'
import { useToast } from '../../hooks/useToast'
import { getCategories } from '../../services/auctionService'
import type { AuctionTab, LotSort } from '../../types/auction'
import type { InfoPanel } from '../../types/ui'
import { filterLots } from '../../utils/catalog'
import './Home.css'

const categories = getCategories()

export default function Home() {
  const elapsed = useElapsedTime()
  const { toast, showToast, dismissToast } = useToast()
  const { lots, activeLot, bidValue, bidError, openBid, closeBid, changeBidValue, submitBid } = useAuction(elapsed, showToast)
  const [tab, setTab] = useState<AuctionTab>('live')
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [reserveOnly, setReserveOnly] = useState(false)
  const [sort, setSort] = useState<LotSort>('ending')
  const [panel, setPanel] = useState<InfoPanel | null>(null)
  const visibleLots = filterLots(lots, { tab, category, query, reserveOnly, sort })
  const showService = (title: string) => setPanel({ title, text: 'Informações do serviço ainda não cadastradas.' })
  const selectTab = (next: AuctionTab) => setTab(next)
  return <>
    <a className="skip-link" href="#catalogo">Ir para os lotes</a>
    <Announcement />
    <Header tab={tab} searchOpen={searchOpen} onToggleSearch={() => setSearchOpen(!searchOpen)} onInfo={setPanel} onService={showService} onSelectTab={selectTab} />
    <section className="container introduction">
      <div className="intro-heading"><div className="intro-copy"><p className="eyebrow gold">Catálogo de leilões</p><h1>Explore os lotes</h1><p className="intro-description">Os lotes serão exibidos aqui quando estiverem disponíveis.</p></div>
        <div className="saleroom-stats"><div><span>Lances Ativos</span><strong>{lots.length} Lotes</strong></div><div><span>Colecionadores</span><strong>0</strong></div><div><span>Salão</span><strong>—</strong></div></div>
      </div>
      <div className="catalog-toolbar"><div className="tabs" role="tablist" aria-label="Status dos lotes">{([{ id: 'live', label: 'Lotes Ao Vivo', count: lots.length }, { id: 'scheduled', label: 'Programados', count: 0 }, { id: 'results', label: 'Resultados', count: 0 }] as const).map(item => <button key={item.id} id={`tab-${item.id}`} role="tab" aria-selected={tab === item.id} aria-controls="catalog-panel" className={tab === item.id ? 'selected' : ''} onClick={() => selectTab(item.id)}>{item.label}<span>{item.count}</span></button>)}</div>
        <div className="categories"><span className="curation-label">Categorias:</span>{categories.map(name => <button className={`category ${category === name ? 'selected' : ''}`} key={name} aria-pressed={category === name} onClick={() => setCategory(category === name ? '' : name)}>{name}</button>)}<button className={`more-filters ${filtersOpen ? 'selected' : ''}`} onClick={() => setFiltersOpen(!filtersOpen)} aria-expanded={filtersOpen} aria-controls="extra-filters"><Icon name="tune" />Mais Filtros{reserveOnly && <span className="live-dot" />}</button></div>
      </div>
      {searchOpen && <div className="search-field" id="catalog-search"><Icon name="search" /><input autoFocus aria-label="Buscar lotes" placeholder="Buscar por nome ou número do lote…" value={query} onChange={event => setQuery(event.target.value)} /><button className="icon-button" aria-label="Limpar e fechar busca" onClick={() => { setQuery(''); setSearchOpen(false) }}><Icon name="close" /></button></div>}
      {filtersOpen && <div className="extra-filters" id="extra-filters"><label><input type="checkbox" checked={reserveOnly} onChange={event => setReserveOnly(event.target.checked)} />Apenas reserva atingida</label><label>Ordenar por<select value={sort} onChange={event => setSort(event.target.value as LotSort)}><option value="ending">Encerramento mais próximo</option><option value="price-high">Maior lance</option><option value="price-low">Menor lance</option></select></label><button onClick={() => { setCategory(''); setReserveOnly(false); setSort('ending'); setQuery('') }}>Limpar filtros</button></div>}
    </section>
    <main className="container catalog" id="catalogo"><div role="tabpanel" id="catalog-panel" aria-labelledby={`tab-${tab}`}>
      {visibleLots.length ? <div className="lot-grid">{visibleLots.map(lot => <LotCard key={lot.id} lot={lot} elapsed={elapsed} onBid={openBid} />)}</div> : <div className="empty-state"><p className="eyebrow gold">Catálogo</p><h2>{tab === 'scheduled' ? 'Nenhum lote programado.' : tab === 'results' ? 'Nenhum resultado disponível.' : 'Nenhum lote encontrado.'}</h2><p>{tab === 'scheduled' ? 'Os próximos leilões serão exibidos aqui.' : tab === 'results' ? 'Os resultados serão exibidos aqui quando disponíveis.' : lots.length ? 'Experimente outra busca ou categoria.' : 'Nenhum lote cadastrado.'}</p><button className="text-link" onClick={() => { selectTab('live'); setCategory(''); setQuery(''); setReserveOnly(false) }}>Ver todos os lotes <span aria-hidden="true">→</span></button></div>}
      <div className="pagination"><span>Mostrando {visibleLots.length ? `1–${visibleLots.length}` : '0'} de {visibleLots.length} Lotes {tab === 'live' ? 'ao Vivo' : tab === 'scheduled' ? 'Programados' : 'Encerrados'}</span><nav aria-label="Paginação"><button disabled>Anterior</button><button className="current-page" aria-current={visibleLots.length ? 'page' : undefined} disabled={!visibleLots.length}>{visibleLots.length ? '01' : '—'}</button><button disabled>Próximo</button></nav></div>
    </div></main>
    {activeLot && <BidModal lot={activeLot} bidValue={bidValue} bidError={bidError} onChange={changeBidValue} onClose={closeBid} onSubmit={submitBid} />}
    {panel && <Modal title={panel.title} onClose={() => setPanel(null)}><p className="eyebrow gold">Informações</p><h2>{panel.title}</h2><p className="panel-copy">{panel.text}</p><button className="primary-button confirm-bid" onClick={() => setPanel(null)}>Entendido</button></Modal>}
    {toast && <Toast message={toast} onDismiss={dismissToast} />}
  </>
}
