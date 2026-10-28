import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import Icon from '../../components/Icon'
import LotImage from '../../components/ui/LotImage'
import StatusBadge from '../../components/ui/StatusBadge'
import { ErrorState, LoadingState } from '../../components/ui/States'
import { useAuth } from '../../context/auth-context'
import { useToast } from '../../context/toast-context'
import { useCountdown } from '../../hooks/useCountdown'
import { useLotRoom } from '../../hooks/useLotRoom'
import type { JsonValue } from '../../api/json'
import type { BidHistoryEntry } from '../../types/api'
import { dateTime, money, shortHash } from '../../utils/format'

function attributeText(value: JsonValue): string | null {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number') {
    return String(value)
  }
  if (typeof value === 'boolean') {
    return value ? 'Sim' : 'Não'
  }
  return null
}

function BidRow({ bid }: { bid: BidHistoryEntry }) {
  return (
    <li className={bid.is_mine ? 'bid-row mine' : 'bid-row'}>
      <span className="bid-sequence">#{String(bid.sequence).padStart(3, '0')}</span>
      <span className="bid-alias">{bid.bidder_alias}{bid.is_mine && <em>você</em>}</span>
      <strong>R$ {money(bid.amount)}</strong>
      <time dateTime={bid.placed_at}>{dateTime(bid.placed_at)}</time>
      {bid.hash && <code title={bid.hash}>{shortHash(bid.hash)}</code>}
    </li>
  )
}

export default function LotRoomPage() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  return <LotRoomSession key={`${id}:${user?.id ?? 'anonymous'}`} lotId={id} />
}

function LotRoomSession({ lotId }: { lotId: string }) {
  const { user } = useAuth()
  const { showToast } = useToast()
  const room = useLotRoom(lotId)
  const [amount, setAmount] = useState('')
  const [feedback, setFeedback] = useState<{
    kind: 'error' | 'success'
    message: string
    available: string | null
    minimumBid: string | null
  } | null>(null)
  const countdown = useCountdown(room.lot?.ends_at ?? null, room.lot?.server_time ?? null)
  const lot = room.lot
  const attributes = useMemo(() => {
    if (!lot) {
      return []
    }
    return Object.entries(lot.attributes)
      .slice(0, 10)
      .map(([key, value]) => ({ key, value: attributeText(value) }))
      .filter((entry): entry is { key: string; value: string } => entry.value !== null)
  }, [lot])

  if (room.loading && lot === null) {
    return <div className="container page-section"><LoadingState label="Abrindo a sala do lote…" /></div>
  }
  if (room.error && lot === null) {
    return (
      <div className="container page-section">
        <ErrorState message={room.error} onRetry={() => { void room.reload() }} />
        <p className="center-link"><Link className="text-link" to="/">Voltar para a vitrine</Link></p>
      </div>
    )
  }
  if (lot === null) {
    return <div className="container page-section"><ErrorState message="Lote não encontrado." /></div>
  }

  const isSeller = user?.role === 'SELLER'
  const live = lot.status === 'live' && !countdown.ended
  const canBid = user !== null && user.role === 'BIDDER' && live
  const position = lot.my_position
  const positionBanner = position === null
    ? null
    : position.status === 'leading'
      ? { className: 'position-leading', title: 'Você está ganhando', text: 'Seu lance é o líder atual deste lote.' }
      : position.status === 'outbid'
        ? { className: 'position-outbid', title: 'Você foi superado', text: position.last_amount ? `Seu último lance foi R$ ${money(position.last_amount)}.` : 'Outro licitante está na liderança.' }
        : { className: 'position-neutral', title: 'Você ainda não deu lance', text: 'Acompanhe a sala e envie o primeiro lance.' }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (amount.trim() === '') {
      setFeedback({ kind: 'error', message: 'Informe o valor do lance.', available: null, minimumBid: null })
      return
    }
    const outcome = await room.submitBid(amount)
    if (outcome.ok) {
      setAmount('')
      setFeedback({ kind: 'success', message: 'Lance registrado. Sua posição foi atualizada.', available: null, minimumBid: null })
      showToast(outcome.message, 'Lance registrado')
      return
    }
    setFeedback({
      kind: 'error',
      message: outcome.message,
      available: outcome.available,
      minimumBid: outcome.minimumBid,
    })
  }

  return (
    <div className="container page-section room-page">
      <div className="room-breadcrumb">
        <Link to="/">Vitrine</Link>
        <span aria-hidden="true">/</span>
        <span>Lote {lot.code}</span>
      </div>
      <div className="room-grid">
        <div className="room-visual">
          <LotImage src={lot.image_url} alt={lot.title} className="lot-artwork room-artwork" />
          <div className="room-meta">
            <div><span className="eyebrow">Categoria</span><p>{lot.category || '—'}</p></div>
            <div><span className="eyebrow">Leiloeiro</span><p>{lot.seller_alias || '—'}</p></div>
            <div><span className="eyebrow">Origem</span><p>{lot.source || '—'}</p></div>
          </div>
          {attributes.length > 0 && (
            <dl className="attribute-list">
              {attributes.map(entry => <div key={entry.key}><dt>{entry.key}</dt><dd>{entry.value}</dd></div>)}
            </dl>
          )}
        </div>
        <div className="room-detail">
          <div className="room-title-row">
            <StatusBadge status={lot.status} />
            <span className={`connection-pill connection-${room.connection}`}>
              <span className="live-dot" />
              {room.connection === 'open' ? 'Tempo real' : room.connection === 'connecting' ? 'Conectando' : 'Polling ativo'}
            </span>
          </div>
          <h1>{lot.title}</h1>
          <p className="room-description">{lot.description || 'Sem descrição cadastrada.'}</p>
          <div className="room-price-grid">
            <div>
              <span className="eyebrow">{lot.bids_count > 0 ? 'Lance atual' : 'Lance inicial'}</span>
              <strong className="room-price">R$ {money(lot.current_bid ?? lot.starting_bid)}</strong>
              <span className="room-sub">{lot.bids_count} {lot.bids_count === 1 ? 'lance' : 'lances'}</span>
            </div>
            <div>
              <span className="eyebrow">Próximo lance exato</span>
              <strong className="room-price">R$ {money(lot.minimum_bid)}</strong>
              <span className="room-sub">Incremento de R$ {money(lot.min_increment)}</span>
            </div>
            <div>
              <span className="eyebrow">Encerramento</span>
              <strong className="room-price countdown">{countdown.label}</strong>
              <span className="room-sub">{dateTime(lot.ends_at)}</span>
            </div>
          </div>
          {lot.extension_count > 0 && <p className="room-note">Prorrogado {lot.extension_count}× pelo anti-sniping. Encerramento original: {dateTime(lot.original_ends_at)}.</p>}
          {positionBanner && position !== null && user !== null && (
            <div className={`position-banner ${positionBanner.className}`}>
              <Icon name={position.status === 'leading' ? 'check' : position.status === 'outbid' ? 'alert' : 'clock'} />
              <div><strong>{positionBanner.title}</strong><span>{positionBanner.text}</span></div>
            </div>
          )}
          <div className="room-actions" id="lance">
            {canBid && (
              <form className="bid-form" onSubmit={event => { void submit(event) }}>
                <label htmlFor="room-bid-amount">Valor do lance</label>
                <div className="bid-input">
                  <span>R$</span>
                  <input
                    id="room-bid-amount"
                    inputMode="decimal"
                    placeholder={money(lot.minimum_bid)}
                    value={amount}
                    onChange={event => { setAmount(event.target.value); setFeedback(null) }}
                    aria-describedby="room-bid-help"
                  />
                  <button type="button" className="quick-bid" onClick={() => { setAmount(lot.minimum_bid); setFeedback(null) }}>Usar mínimo</button>
                </div>
                <p id="room-bid-help" className="bid-notice">O valor precisa ser exatamente R$ {money(lot.minimum_bid)}. O identificador do lance é gerado antes do envio e reutilizado em retentativas.</p>
                {feedback && <p className={feedback.kind === 'error' ? 'bid-error' : 'bid-success'} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.message}{feedback.kind === 'error' && <Link className="inline-link" to="/carteira">Ver carteira</Link>}</p>}
                {feedback?.kind === 'error' && (feedback.available !== null || feedback.minimumBid !== null) && (
                  <p className="bid-notice" role="status">
                    {feedback.available !== null && <>Disponível: R$ {money(feedback.available)}</>}
                    {feedback.available !== null && feedback.minimumBid !== null && ' · '}
                    {feedback.minimumBid !== null && <>Lance mínimo: R$ {money(feedback.minimumBid)}</>}
                  </p>
                )}
                <button className="primary-button confirm-bid" type="submit" disabled={room.submitting}>{room.submitting ? 'Enviando…' : 'Confirmar lance'}</button>
              </form>
            )}
            {user === null && (
              <div className="room-callout">
                <p>Entre na sua conta para disputar este lote.</p>
                <Link className="primary-button button-link" to={`/login?next=${encodeURIComponent(`/lotes/${lot.id}`)}`}>Entrar para dar lance</Link>
              </div>
            )}
            {user !== null && isSeller && <div className="room-callout"><p>Leiloeiros acompanham a sala, mas não podem dar lances.</p></div>}
            {user !== null && !isSeller && !live && <div className="room-callout"><p>{lot.status === 'cancelled' ? 'Este lote foi cancelado.' : 'Este lote não está aberto para lances.'}</p></div>}
            {user !== null && user.role === 'BIDDER' && live && <Link className="text-link" to="/carteira">Acompanhar saldo da carteira <span aria-hidden="true">→</span></Link>}
          </div>
          <div className="room-links">
            <Link to={`/lotes/${lot.id}/auditoria`}><Icon name="shield" /> Auditoria pública</Link>
            {lot.source_url && <a href={lot.source_url} target="_blank" rel="noreferrer"><Icon name="external" /> Fonte do item</a>}
          </div>
        </div>
      </div>
      <section className="history-section" aria-labelledby="history-heading">
        <div className="section-heading-row">
          <div>
            <p className="eyebrow gold">Cadeia de lances</p>
            <h2 id="history-heading">Histórico da sala</h2>
          </div>
          <span className="result-count">{room.bidsCount} registros</span>
        </div>
        {room.historyError && <ErrorState message={room.historyError} onRetry={() => { void room.reload() }} />}
        {room.bids.length === 0
          ? <p className="muted-copy">Nenhum lance registrado até agora.</p>
          : <ol className="bid-list">{room.bids.map(bid => <BidRow key={`${bid.sequence}-${bid.placed_at}`} bid={bid} />)}</ol>}
        {room.hasMoreBids && <button className="text-link load-more" onClick={() => { void room.loadMoreBids() }}>Carregar mais lances <span aria-hidden="true">→</span></button>}
      </section>
    </div>
  )
}
