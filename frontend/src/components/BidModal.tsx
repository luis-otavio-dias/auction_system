import type { FormEvent } from 'react'
import type { Lot } from '../types/auction'
import { money } from '../utils/format'
import Modal from './Modal'

export default function BidModal({ lot, bidValue, bidError, onChange, onClose, onSubmit }: {
  lot: Lot
  bidValue: string
  bidError: string
  onChange: (value: string) => void
  onClose: () => void
  onSubmit: (event: FormEvent) => void
}) {
  return <Modal title={`Lance para o lote ${lot.id}`} onClose={onClose}><p className="eyebrow gold">Lote {lot.id.padStart(3, '0')} • Demonstração</p><h2>{lot.title}</h2><div className="modal-prices"><div><span className="eyebrow">Lance Líder</span><strong>{money(lot.bid)}</strong></div><div><span className="eyebrow">Próximo Mínimo</span><strong className="green">{money(lot.bid + lot.increment)}</strong></div></div><form onSubmit={onSubmit}><label className="eyebrow" htmlFor="bid-amount">Valor do lance</label><div className="bid-input"><span>—</span><input id="bid-amount" type="number" required min={lot.bid + lot.increment} step="1" value={bidValue} onChange={event => { onChange(event.target.value) }} aria-describedby="bid-notice bid-error" /></div><p className="bid-notice" id="bid-notice">Condições do leilão ainda não disponíveis.</p><div className="bid-increments">{[lot.increment, lot.increment * 2, lot.increment * 3].map(amount => <button type="button" key={amount} onClick={() => onChange(String((Number(bidValue) || 0) + amount))}>+{money(amount)}</button>)}</div>{bidError && <p className="bid-error" id="bid-error" role="alert">{bidError}</p>}<button className="primary-button confirm-bid" type="submit">Confirmar Lance Demonstrativo</button></form></Modal>
}
