import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { fetchMyBids, fetchMyWins } from '../../api/lots'
import Icon from '../../components/Icon'
import { ErrorState, LoadingState } from '../../components/ui/States'
import type { MyBid, Paginated, WinRecord } from '../../types/api'
import { errorMessage } from '../../utils/errors'
import { dateTime, money } from '../../utils/format'

function receiptHref(win: WinRecord): string {
  return win.share_url || `/comprovantes/${win.receipt_token}`
}

export default function WinsPage() {
  const [wins, setWins] = useState<WinRecord[] | null>(null)
  const [bids, setBids] = useState<Paginated<MyBid> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [bidsError, setBidsError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setWins(null)
      setBids(null)
      const [winsResult, bidsResult] = await Promise.allSettled([
        fetchMyWins(),
        fetchMyBids(),
      ])
      if (controller.signal.aborted) {
        return
      }
      if (winsResult.status === 'fulfilled') {
        setWins(winsResult.value)
        setError(null)
      } else if (winsResult.reason instanceof Error) {
        setError(errorMessage(winsResult.reason, 'Não foi possível carregar seus arremates.'))
      }
      if (bidsResult.status === 'fulfilled') {
        setBids(bidsResult.value)
        setBidsError(null)
      } else if (bidsResult.reason instanceof Error) {
        const forbidden = bidsResult.reason instanceof ApiError && bidsResult.reason.status === 403
        setBidsError(forbidden ? null : errorMessage(bidsResult.reason, 'Não foi possível carregar seus lances.'))
      }
    }
    void load()
    return () => controller.abort()
  }, [reloadKey])

  const bidRows = bids?.results ?? []

  return (
    <div className="container page-section">
      <div className="page-heading">
        <p className="eyebrow gold">Meus arremates</p>
        <h1>Lotes vencidos por você</h1>
        <p className="intro-description">Cada arremate liquidado gera um comprovante público sem dados pessoais, compartilhável por link.</p>
      </div>
      {error && <ErrorState message={error} onRetry={() => setReloadKey(value => value + 1)} />}
      {wins === null && !error && <LoadingState label="Carregando arremates…" />}
      {wins !== null && wins.length === 0 && (
        <div className="empty-state">
          <p className="eyebrow gold">Arremates</p>
          <h2>Nenhum lote arrematado ainda.</h2>
          <p>Participe de um pregão ao vivo para disputar lotes.</p>
          <Link className="text-link" to="/">Ir para a vitrine <span aria-hidden="true">→</span></Link>
        </div>
      )}
      {wins !== null && wins.length > 0 && (
        <div className="win-grid">
          {wins.map((win, index) => (
            <article className="win-card" key={`${win.lot_code}-${index}`}>
              <div className="win-body">
                <span className="eyebrow">Lote {win.lot_code}</span>
                <h2>{win.title}</h2>
                <div className="win-metrics">
                  <div><span>Valor final</span><strong>R$ {money(win.final_price ?? '0.00')}</strong></div>
                  <div><span>Emitido em</span><strong>{dateTime(win.issued_at ?? win.settled_at)}</strong></div>
                </div>
                <div className="win-actions">
                  {win.share_url
                    ? <a className="primary-button button-link" href={win.share_url} target="_blank" rel="noreferrer"><Icon name="receipt" /> Abrir comprovante</a>
                    : <Link className="primary-button button-link" to={receiptHref(win)}><Icon name="receipt" /> Abrir comprovante</Link>}
                  {win.lot_id && <Link className="text-link" to={`/lotes/${win.lot_id}`}>Ver lote <span aria-hidden="true">→</span></Link>}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <section className="panel-card">
        <div className="panel-heading"><p className="eyebrow gold">Participação</p><h2>Lotes em que você deu lance</h2></div>
        {bids === null && bidsError === null && <LoadingState label="Carregando seus lances…" />}
        {bidsError && <ErrorState message={bidsError} onRetry={() => setReloadKey(value => value + 1)} />}
        {bids !== null && bidRows.length === 0 && <p className="muted-copy">Você ainda não registrou lances.</p>}
        {bidRows.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Lote</th><th>Lance</th><th>Data</th></tr></thead>
              <tbody>
                {bidRows.map(bid => (
                  <tr key={`${bid.lot_id ?? bid.lot_code}-${bid.sequence}`}>
                    <td>
                      {bid.lot_id ? <Link to={`/lotes/${bid.lot_id}`}>{bid.lot_code || `Lote ${bid.sequence}`}</Link> : bid.lot_code || '—'}
                      <span className="cell-note">{bid.lot_title}</span>
                    </td>
                    <td>R$ {money(bid.amount)}</td>
                    <td>{dateTime(bid.placed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
