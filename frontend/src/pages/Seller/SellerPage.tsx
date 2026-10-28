import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { searchCatalog } from '../../api/catalog'
import { cancelLot, createLot, fetchSellerLots, fetchSellerSummary } from '../../api/lots'
import Icon from '../../components/Icon'
import PaginationControls from '../../components/ui/PaginationControls'
import StatusBadge from '../../components/ui/StatusBadge'
import { ErrorState, LoadingState } from '../../components/ui/States'
import { useToast } from '../../context/toast-context'
import type { CatalogItem, Paginated, SellerLot, SellerSummary } from '../../types/api'
import { errorMessage } from '../../utils/errors'
import { dateTime, money, parseAmount } from '../../utils/format'

function toLocalInput(date: Date): string {
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16)
}

export default function SellerPage() {
  const { showToast } = useToast()
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<CatalogItem[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchDegraded, setSearchDegraded] = useState(false)
  const [selected, setSelected] = useState<CatalogItem | null>(null)
  const [startsAt, setStartsAt] = useState(() => toLocalInput(new Date(Date.now() + 3600 * 1000)))
  const [endsAt, setEndsAt] = useState(() => toLocalInput(new Date(Date.now() + 24 * 3600 * 1000)))
  const [startingBid, setStartingBid] = useState('500.00')
  const [minIncrement, setMinIncrement] = useState('25.00')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [lots, setLots] = useState<Paginated<SellerLot> | null>(null)
  const [lotsPage, setLotsPage] = useState(1)
  const [lotsLoading, setLotsLoading] = useState(true)
  const [lotsError, setLotsError] = useState<string | null>(null)
  const [summary, setSummary] = useState<SellerSummary | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [cancelId, setCancelId] = useState<string | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [canceling, setCanceling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const loadLots = async () => {
      setLotsLoading(true)
      try {
        const result = await fetchSellerLots(lotsPage)
        if (!controller.signal.aborted) {
          setLots(result)
          setLotsError(null)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          setLotsError(errorMessage(cause, 'Não foi possível carregar seus lotes.'))
        }
      } finally {
        if (!controller.signal.aborted) {
          setLotsLoading(false)
        }
      }
    }
    void loadLots()
    return () => controller.abort()
  }, [reloadKey, lotsPage])

  useEffect(() => {
    const controller = new AbortController()
    const loadSummary = async () => {
      try {
        const result = await fetchSellerSummary()
        if (!controller.signal.aborted) {
          setSummary(result)
          setSummaryError(null)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          setSummaryError(errorMessage(cause, 'Resumo de vendas indisponível.'))
        }
      }
    }
    void loadSummary()
    return () => controller.abort()
  }, [reloadKey])

  const runSearch = async (event: FormEvent) => {
    event.preventDefault()
    if (searchTerm.trim() === '') {
      setSearchError('Informe um termo para buscar na AIC.')
      return
    }
    setSearching(true)
    setSearchError(null)
    setSearchDegraded(false)
    try {
      const result = await searchCatalog(searchTerm.trim())
      setSearchResults(result.results)
      setSearchDegraded(result.degraded)
      if (result.results.length === 0) {
        setSearchError('Nenhum item encontrado na AIC.')
      }
    } catch (cause) {
      setSearchResults([])
      if (cause instanceof Error) {
        setSearchError(errorMessage(cause, 'Não foi possível consultar a AIC.'))
      }
    } finally {
      setSearching(false)
    }
  }

  const submitLot = async (event: FormEvent) => {
    event.preventDefault()
    if (selected === null) {
      setCreateError('Selecione um item da AIC antes de criar o lote.')
      return
    }
    const start = new Date(startsAt)
    const end = new Date(endsAt)
    const starting = parseAmount(startingBid)
    const increment = parseAmount(minIncrement)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      setCreateError('Informe datas válidas para abertura e encerramento.')
      return
    }
    if (end <= start) {
      setCreateError('O encerramento precisa ser posterior à abertura.')
      return
    }
    if (starting === null || starting <= 0 || increment === null || increment <= 0) {
      setCreateError('Lance inicial e incremento devem ser maiores que zero.')
      return
    }
    setCreating(true)
    setCreateError(null)
    try {
      await createLot({
        catalog_item_id: selected.id,
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
        starting_bid: starting.toFixed(2),
        min_increment: increment.toFixed(2),
      })
      showToast('Lote criado e publicado na vitrine.', 'Lote criado')
      setSelected(null)
      setSearchResults([])
      setSearchTerm('')
      setLotsPage(1)
      setReloadKey(value => value + 1)
    } catch (cause) {
      if (cause instanceof ApiError) {
        setCreateError(cause.detail || 'Não foi possível criar o lote.')
      } else if (cause instanceof Error) {
        setCreateError(errorMessage(cause, 'Não foi possível criar o lote.'))
      }
    } finally {
      setCreating(false)
    }
  }

  const confirmCancel = async () => {
    if (cancelId === null) {
      return
    }
    setCanceling(true)
    setCancelError(null)
    try {
      await cancelLot(cancelId, cancelReason)
      showToast('Lote cancelado. Ele não aparece mais na vitrine.', 'Lote cancelado')
      setCancelId(null)
      setCancelReason('')
      setReloadKey(value => value + 1)
    } catch (cause) {
      if (cause instanceof ApiError) {
        setCancelError(cause.detail || 'Não foi possível cancelar o lote.')
      } else if (cause instanceof Error) {
        setCancelError(errorMessage(cause, 'Não foi possível cancelar o lote.'))
      }
    } finally {
      setCanceling(false)
    }
  }

  return (
    <div className="container page-section">
      <div className="page-heading">
        <p className="eyebrow gold">Painel do leiloeiro</p>
        <h1>Curadoria e resultados</h1>
        <p className="intro-description">Busque itens na Art Institute of Chicago, publique lotes e acompanhe o resultado financeiro de cada arremate.</p>
      </div>
      <section className="panel-card">
        <div className="panel-heading"><p className="eyebrow gold">Catálogo AIC</p><h2>Buscar item</h2></div>
        <form className="catalog-search-bar inline-search" onSubmit={event => { void runSearch(event) }}>
          <Icon name="search" />
          <input aria-label="Buscar item na AIC" placeholder="Ex.: Monet, paisagem, cerâmica…" value={searchTerm} onChange={event => setSearchTerm(event.target.value)} />
          <button className="primary-button search-submit" type="submit" disabled={searching}>{searching ? 'Buscando…' : 'Buscar'}</button>
        </form>
        {searchError && <p className="bid-error" role="alert">{searchError}</p>}
        {searchDegraded && searchResults.length > 0 && (
          <p className="catalog-degraded" role="status">
            Catálogo externo indisponível no momento. Exibindo o acervo local de demonstração.
          </p>
        )}
        {searchResults.length > 0 && (
          <div className="catalog-picker">
            {searchResults.map(item => (
              <button key={item.id} type="button" className={selected?.id === item.id ? 'picker-item selected' : 'picker-item'} onClick={() => { setSelected(item); setCreateError(null) }}>
                <span className="picker-image">{item.thumbnail_url || item.image_url ? <img src={item.thumbnail_url || item.image_url} alt="" loading="lazy" /> : 'Sem imagem'}</span>
                <span><strong>{item.title}</strong><em>{item.category || item.source}</em></span>
              </button>
            ))}
          </div>
        )}
        {selected && (
          <form className="lot-form" onSubmit={event => { void submitLot(event) }}>
            <div className="selected-item">
              {selected.image_url && <img src={selected.image_url} alt="" />}
              <div><span className="eyebrow">Item selecionado</span><strong>{selected.title}</strong><p>{selected.external_id}</p></div>
              <button type="button" className="text-button" onClick={() => setSelected(null)}>Trocar</button>
            </div>
            <div className="form-grid">
              <label>Abertura<input type="datetime-local" value={startsAt} onChange={event => setStartsAt(event.target.value)} required /></label>
              <label>Encerramento<input type="datetime-local" value={endsAt} onChange={event => setEndsAt(event.target.value)} required /></label>
              <label>Lance inicial (R$)<input inputMode="decimal" value={startingBid} onChange={event => setStartingBid(event.target.value)} required /></label>
              <label>Incremento mínimo (R$)<input inputMode="decimal" value={minIncrement} onChange={event => setMinIncrement(event.target.value)} required /></label>
            </div>
            {createError && <p className="bid-error" role="alert">{createError}</p>}
            <button className="primary-button confirm-bid" type="submit" disabled={creating}>{creating ? 'Publicando…' : 'Criar lote'}</button>
          </form>
        )}
      </section>

      <section className="panel-card">
        <div className="panel-heading"><p className="eyebrow gold">Seus lotes</p><h2>Publicados</h2></div>
        {lotsLoading && <LoadingState label="Carregando seus lotes…" />}
        {!lotsLoading && lotsError && <ErrorState message={lotsError} onRetry={() => setReloadKey(value => value + 1)} />}
        {!lotsLoading && !lotsError && lots && lots.results.length === 0 && <p className="muted-copy">Você ainda não criou lotes.</p>}
        {lots && lots.results.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Lote</th><th>Status</th><th>Lances</th><th>Valor</th><th>Encerramento</th><th>Ações</th></tr></thead>
                <tbody>
                  {lots.results.map(lot => {
                    const canCancel = lot.bids_count === 0 && (lot.status === 'live' || lot.status === 'scheduled')
                    return (
                      <tr key={lot.id}>
                        <td><Link to={`/lotes/${lot.id}`}>{lot.code}</Link><span className="cell-note">{lot.title}</span></td>
                        <td><StatusBadge status={lot.status} /></td>
                        <td>{lot.bids_count}</td>
                        <td>R$ {money(lot.current_bid ?? lot.starting_bid)}</td>
                        <td>{dateTime(lot.ends_at)}</td>
                        <td className="table-actions">
                          <Link className="text-button" to={`/lotes/${lot.id}`}>Abrir</Link>
                          {canCancel && <button className="text-button danger" onClick={() => { setCancelId(lot.id); setCancelReason(''); setCancelError(null) }}>Cancelar</button>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <PaginationControls
              page={lotsPage}
              hasNext={lots.next !== null}
              hasPrevious={lots.previous !== null}
              onNext={() => setLotsPage(current => current + 1)}
              onPrevious={() => setLotsPage(current => Math.max(1, current - 1))}
            />
          </>
        )}
        {cancelId !== null && (
          <div className="confirm-box">
            <p>Cancele o lote apenas enquanto não houver lances. O motivo fica registrado.</p>
            <label>Motivo do cancelamento
              <input value={cancelReason} onChange={event => setCancelReason(event.target.value)} placeholder="Opcional" maxLength={255} />
            </label>
            {cancelError && <p className="bid-error" role="alert">{cancelError}</p>}
            <div className="confirm-actions">
              <button className="primary-button" onClick={() => { void confirmCancel() }} disabled={canceling}>{canceling ? 'Cancelando…' : 'Confirmar cancelamento'}</button>
              <button type="button" className="text-button" onClick={() => setCancelId(null)}>Voltar</button>
            </div>
          </div>
        )}
      </section>

      <section className="panel-card">
        <div className="panel-heading"><p className="eyebrow gold">Resultados</p><h2>Total recebido</h2></div>
        {summaryError && <ErrorState message={summaryError} onRetry={() => setReloadKey(value => value + 1)} />}
        {summary === null && !summaryError && <LoadingState label="Carregando resumo…" />}
        {summary && (
          <>
            <div className="wallet-grid compact">
              <div className="metric-card available"><span>Total recebido</span><strong>R$ {money(summary.total_received)}</strong></div>
              <div className="metric-card"><span>Lotes liquidados</span><strong>{summary.settled_count}</strong></div>
              <div className="metric-card"><span>Lotes sem arremate</span><strong>{summary.unsold_count}</strong></div>
              <div className="metric-card"><span>Lotes bloqueados</span><strong>{summary.blocked_lots.length}</strong></div>
            </div>
            <div className="panel-heading sub-heading"><p className="eyebrow gold">Resultado por lote</p><h3>Lotes liquidados</h3></div>
            {summary.results.length === 0
              ? <p className="muted-copy">Nenhum lote liquidado ainda.</p>
              : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead><tr><th>Lote</th><th>Vencedor</th><th>Valor final</th><th>Liquidado em</th></tr></thead>
                    <tbody>
                      {summary.results.map(item => (
                        <tr key={`${item.lot_id}-${item.code}`}>
                          <td>
                            {item.lot_id ? <Link to={`/lotes/${item.lot_id}`}>{item.code}</Link> : item.code}
                            <span className="cell-note">{item.title}</span>
                          </td>
                          <td>{item.winner_alias || '—'}</td>
                          <td>R$ {money(item.final_price)}</td>
                          <td>{dateTime(item.settled_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            <div className="panel-heading sub-heading"><p className="eyebrow gold">Sem arremate</p><h3>Lotes encerrados sem vencedor</h3></div>
            {summary.unsold_lots.length === 0
              ? <p className="muted-copy">Nenhum lote encerrado sem arremate.</p>
              : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead><tr><th>Lote</th><th>Encerrado em</th></tr></thead>
                    <tbody>
                      {summary.unsold_lots.map(item => (
                        <tr key={`${item.lot_id}-${item.code}`}>
                          <td>
                            {item.lot_id ? <Link to={`/lotes/${item.lot_id}`}>{item.code}</Link> : item.code}
                            <span className="cell-note">{item.title}</span>
                          </td>
                          <td>{dateTime(item.ends_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            <div className="panel-heading sub-heading"><p className="eyebrow gold">Bloqueios</p><h3>Lotes com erro de liquidação</h3></div>
            {summary.blocked_lots.length === 0
              ? <p className="muted-copy">Nenhum lote bloqueado por inconsistência de liquidação.</p>
              : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead><tr><th>Lote</th><th>Motivo do bloqueio</th></tr></thead>
                    <tbody>
                      {summary.blocked_lots.map(item => (
                        <tr key={`${item.lot_id ?? item.code}-${item.settlement_error}`}>
                          <td>
                            {item.lot_id ? <Link to={`/lotes/${item.lot_id}`}>{item.code}</Link> : item.code}
                            {item.title && <span className="cell-note">{item.title}</span>}
                          </td>
                          <td className="danger">{item.settlement_error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </>
        )}
      </section>
    </div>
  )
}
