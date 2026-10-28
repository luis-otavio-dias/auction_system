import { Link } from 'react-router-dom'
import type { LotSummary } from '../../types/api'
import { money } from '../../utils/format'
import { useCountdown } from '../../hooks/useCountdown'
import LotImage from '../ui/LotImage'
import StatusBadge from '../ui/StatusBadge'

export default function CatalogLotCard({ lot, serverTime }: { lot: LotSummary; serverTime: string | null }) {
  const ends = useCountdown(lot.ends_at, serverTime)
  const starts = useCountdown(lot.starts_at, serverTime)
  const live = lot.status === 'live'
  const current = lot.current_bid ?? lot.starting_bid
  return (
    <article className="lot">
      <Link to={`/lotes/${lot.id}`} aria-label={`Abrir ${lot.title}`}>
        <div className="lot-artwork-wrap">
          <LotImage src={lot.image_url} alt={lot.title} />
          <span className="lot-number">Lote {lot.code || lot.id.slice(0, 8)}</span>
          {lot.status !== 'ended' && (
            <span className="lot-timer">
              <span className="live-dot" />
              {live ? ends.label : starts.ended ? 'Aguardando' : `Abre em ${starts.label}`}
            </span>
          )}
        </div>
      </Link>
      <div className="lot-details">
        <div className="lot-metadata">
          <span>{lot.category || 'Leilão'}</span>
          <StatusBadge status={lot.status} />
        </div>
        <h2><Link to={`/lotes/${lot.id}`}>{lot.title}</Link></h2>
        <p>{live ? 'Lance ao vivo nesta sala.' : lot.status === 'scheduled' ? 'Lote programado para abertura.' : 'Lote encerrado.'}</p>
      </div>
      <div className="lot-bidding">
        <div className="lot-prices">
          <div>
            <span className="eyebrow">{lot.bids_count > 0 ? 'Lance atual' : 'Lance inicial'}</span>
            <strong>R$ {money(current)}</strong>
          </div>
          <div className="estimate">
            <span className="eyebrow">{lot.bids_count > 0 ? 'Próximo mínimo' : 'Incremento'}</span>
            <span>R$ {money(lot.minimum_bid)}</span>
          </div>
        </div>
        <div className="bid-actions">
          <Link className="primary-button button-link" to={`/lotes/${lot.id}`}>{live ? 'Entrar na sala' : 'Ver lote'}</Link>
          <Link className="quick-bid button-link" to={`/lotes/${lot.id}#lance`} aria-label={`Ir para o formulário de lance do lote ${lot.code}`}>+{money(lot.min_increment)}</Link>
        </div>
      </div>
    </article>
  )
}
