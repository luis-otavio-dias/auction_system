import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { listLots, getLot } from '../../api/lots'
import CatalogLotCard from '../../components/catalog/CatalogLotCard'
import Icon from '../../components/Icon'
import PaginationControls from '../../components/ui/PaginationControls'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import type { LotSort, LotSummary, LotTab, Paginated } from '../../types/api'
import { errorMessage } from '../../utils/errors'

const TAB_LABELS: Record<LotTab, { label: string; empty: string; description: string }> = {
  live: { label: 'Lotes ao vivo', empty: 'Nenhum lote ao vivo.', description: 'Lotes abertos para lances agora.' },
  scheduled: { label: 'Programados', empty: 'Nenhum lote programado.', description: 'Próximos pregões já cadastrados.' },
  ended: { label: 'Resultados', empty: 'Nenhum resultado disponível.', description: 'Lotes encerrados e liquidados.' },
}

const SORT_LABELS: Record<LotSort, string> = {
  ending: 'Encerramento mais próximo',
  'price-high': 'Maior lance',
  'price-low': 'Menor lance',
  recent: 'Mais recentes',
}

export default function CatalogPage() {
  const [tab, setTab] = useState<LotTab>('live')
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<LotSort>('ending')
  const [page, setPage] = useState(1)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [data, setData] = useState<Paginated<LotSummary> | null>(null)
  const [counts, setCounts] = useState<Record<LotTab, number>>({ live: 0, scheduled: 0, ended: 0 })
  const [categories, setCategories] = useState<string[]>([])
  const [serverTime, setServerTime] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      try {
        const result = await listLots({ tab, q: query, category, sort, page }, controller.signal)
        setData(result)
        setError(null)
        const found = result.results.map(lot => lot.category).filter(name => name !== '')
        if (found.length > 0) {
          setCategories(current => [...new Set([...current, ...found])])
        }
      } catch (cause) {
        if (controller.signal.aborted || !(cause instanceof Error)) {
          return
        }
        setError(errorMessage(cause, 'Não foi possível carregar a vitrine.'))
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [tab, query, category, sort, page, reloadKey])

  useEffect(() => {
    const controller = new AbortController()
    const loadCounts = async () => {
      try {
        const [live, scheduled, ended] = await Promise.all([
          listLots({ tab: 'live', q: '', category: '', sort: 'ending', page: 1 }, controller.signal),
          listLots({ tab: 'scheduled', q: '', category: '', sort: 'ending', page: 1 }, controller.signal),
          listLots({ tab: 'ended', q: '', category: '', sort: 'ending', page: 1 }, controller.signal),
        ])
        if (controller.signal.aborted) {
          return
        }
        setCounts({ live: live.count, scheduled: scheduled.count, ended: ended.count })
        const names = [...live.results, ...scheduled.results, ...ended.results]
          .map(lot => lot.category)
          .filter(name => name !== '')
        setCategories(current => [...new Set([...current, ...names])])
      } catch {
        return
      }
    }
    void loadCounts()
    return () => controller.abort()
  }, [reloadKey])

  useEffect(() => {
    const first = data?.results[0]
    if (!first || serverTime !== null) {
      return
    }
    let active = true
    getLot(first.id)
      .then(detail => {
        if (active) {
          setServerTime(detail.server_time)
        }
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [data, serverTime])

  const selectTab = useCallback((next: LotTab) => {
    setTab(next)
    setPage(1)
  }, [])

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    setQuery(queryInput.trim())
    setPage(1)
  }

  const clearFilters = () => {
    setCategory('')
    setSort('ending')
    setQuery('')
    setQueryInput('')
    setPage(1)
  }

  const lots = useMemo(() => (data?.results ?? []).filter(lot => lot.status !== 'cancelled'), [data])

  return (
    <>
      <section className="container introduction">
        <div className="intro-heading">
          <div className="intro-copy">
            <p className="eyebrow gold">Catálogo de leilões</p>
            <h1>Explore os lotes</h1>
            <p className="intro-description">Dispute obras selecionadas com lances exatos, carteira comprometida e histórico público verificável.</p>
          </div>
          <div className="saleroom-stats">
            <div><span>Lotes ao vivo</span><strong>{counts.live}</strong></div>
            <div><span>Programados</span><strong>{counts.scheduled}</strong></div>
            <div><span>Resultados</span><strong>{counts.ended}</strong></div>
          </div>
        </div>
        <form className="catalog-search-bar" role="search" onSubmit={submitSearch}>
          <Icon name="search" />
          <input
            aria-label="Buscar lotes por título, código ou categoria"
            placeholder="Buscar por título, código ou categoria…"
            value={queryInput}
            onChange={event => setQueryInput(event.target.value)}
          />
          <button className="primary-button search-submit" type="submit">Buscar</button>
          {query && <button type="button" className="text-button" onClick={() => { setQuery(''); setQueryInput(''); setPage(1) }}>Limpar</button>}
        </form>
        <div className="catalog-toolbar">
          <div className="tabs" role="tablist" aria-label="Status dos lotes">
            {(Object.keys(TAB_LABELS) as LotTab[]).map(item => (
              <button
                key={item}
                role="tab"
                aria-selected={tab === item}
                className={tab === item ? 'selected' : ''}
                onClick={() => selectTab(item)}
              >
                {TAB_LABELS[item].label}<span>{counts[item]}</span>
              </button>
            ))}
          </div>
          <div className="categories">
            <span className="curation-label">Categorias:</span>
            {categories.slice(0, 8).map(name => (
              <button
                className={`category ${category === name ? 'selected' : ''}`}
                key={name}
                aria-pressed={category === name}
                onClick={() => { setCategory(category === name ? '' : name); setPage(1) }}
              >
                {name}
              </button>
            ))}
            <button className={`more-filters ${filtersOpen ? 'selected' : ''}`} onClick={() => setFiltersOpen(!filtersOpen)} aria-expanded={filtersOpen}>
              <Icon name="tune" />Mais filtros{(category || sort !== 'ending') && <span className="live-dot" />}
            </button>
          </div>
        </div>
        {filtersOpen && (
          <div className="extra-filters">
            <label>
              Ordenar por
              <select value={sort} onChange={event => { setSort(event.target.value as LotSort); setPage(1) }}>
                {(Object.keys(SORT_LABELS) as LotSort[]).map(value => <option key={value} value={value}>{SORT_LABELS[value]}</option>)}
              </select>
            </label>
            <label>
              Categoria
              <select value={category} onChange={event => { setCategory(event.target.value); setPage(1) }}>
                <option value="">Todas as categorias</option>
                {categories.map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
            <button type="button" onClick={clearFilters}>Limpar filtros</button>
          </div>
        )}
      </section>
      <section className="container catalog" id="catalogo" aria-labelledby="catalog-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow gold">{TAB_LABELS[tab].description}</p>
            <h2 id="catalog-heading">{TAB_LABELS[tab].label}</h2>
          </div>
          {data && <span className="result-count">{data.count} {data.count === 1 ? 'lote' : 'lotes'}</span>}
        </div>
        {loading && <LoadingState label="Carregando lotes…" />}
        {!loading && error && <ErrorState message={error} onRetry={() => setReloadKey(value => value + 1)} />}
        {!loading && !error && lots.length === 0 && (
          <EmptyState
            title={TAB_LABELS[tab].empty}
            text="Ajuste a busca ou acompanhe os próximos pregões."
            action={<Link className="text-link" to="/">Atualizar vitrine <span aria-hidden="true">→</span></Link>}
          />
        )}
        {!loading && !error && lots.length > 0 && (
          <>
            <div className="lot-grid">
              {lots.map(lot => <CatalogLotCard key={lot.id} lot={lot} serverTime={serverTime} />)}
            </div>
            <div className="pagination-row">
              <span>Mostrando {lots.length} de {data?.count ?? lots.length} lotes</span>
              <PaginationControls
                page={page}
                hasNext={data?.next !== null && data?.next !== undefined}
                hasPrevious={data?.previous !== null && data?.previous !== undefined}
                onNext={() => { setPage(current => current + 1); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                onPrevious={() => { setPage(current => Math.max(1, current - 1)); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
              />
            </div>
          </>
        )}
      </section>
    </>
  )
}
