import type { Lot } from '../types/auction'
import { clock, money } from '../utils/format'

export default function LotCard({ lot, elapsed, onBid }: { lot: Lot; elapsed: number; onBid: (lot: Lot) => void }) {
  return <article className="lot">
        <div className="lot-artwork">{lot.image ? <img src={lot.image} alt={lot.alt} loading="eager" width="800" height="600" /> : <div className="image-placeholder">Sem imagem</div>}<span className="lot-number">Lote {lot.id.padStart(3, '0')}</span><span className="lot-timer"><span className="live-dot" />{lot.seconds > elapsed ? clock(lot.seconds - elapsed) : 'Encerrado'}</span></div>
        <div className="lot-details"><div className="lot-metadata"><span>{lot.provenance}</span><span className={lot.status === 'Reserva Atingida' ? 'green' : lot.status === 'Inspecionado' ? '' : 'gold'}>{lot.status}</span></div><h2>{lot.title}</h2><p>{lot.description}</p></div>
        <div className="lot-bidding"><div className="lot-prices"><div><span className="eyebrow">Lance Atual no Salão</span><strong>{money(lot.bid)}</strong></div><div className="estimate"><span className="eyebrow">Estimativa Oficial</span><span>{lot.estimate}</span></div></div><div className="bid-actions"><button className="primary-button" disabled={elapsed >= lot.seconds} onClick={() => onBid(lot)}>{elapsed >= lot.seconds ? 'Pregão Encerrado' : 'Fazer Lance'}</button><button className="quick-bid" disabled={elapsed >= lot.seconds} title={`Preparar lance de ${money(lot.bid + lot.increment)}`} onClick={() => onBid(lot)}>+{money(lot.increment)}</button></div></div>
      </article>
}
