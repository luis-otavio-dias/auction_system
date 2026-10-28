import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchReceipt, verifyReceipt } from '../../api/catalog'
import Icon from '../../components/Icon'
import LotImage from '../../components/ui/LotImage'
import { ErrorState, LoadingState } from '../../components/ui/States'
import type { Receipt, ReceiptVerification } from '../../types/api'
import { errorMessage } from '../../utils/errors'
import { dateTime, money, shortHash } from '../../utils/format'

export default function ReceiptPage() {
  const { token = '' } = useParams()
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [verification, setVerification] = useState<ReceiptVerification | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setReceipt(null)
      setVerification(null)
      try {
        const [receiptResult, verificationResult] = await Promise.allSettled([
          fetchReceipt(token, controller.signal),
          verifyReceipt(token, controller.signal),
        ])
        if (controller.signal.aborted) {
          return
        }
        if (receiptResult.status === 'fulfilled') {
          setReceipt(receiptResult.value)
          setError(null)
        } else if (receiptResult.reason instanceof Error) {
          setError(errorMessage(receiptResult.reason, 'Comprovante não encontrado.'))
        }
        if (verificationResult.status === 'fulfilled') {
          setVerification(verificationResult.value)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          setError(errorMessage(cause, 'Não foi possível carregar o comprovante.'))
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [token, reloadKey])

  const shareUrl = useMemo(() => {
    if (receipt?.share_url) {
      return receipt.share_url
    }
    if (typeof window === 'undefined') {
      return ''
    }
    return window.location.href
  }, [receipt])

  const copyLink = async () => {
    if (shareUrl === '') {
      return
    }
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="container page-section">
      <div className="page-heading">
        <p className="eyebrow gold">Comprovante público</p>
        <h1>Arremate registrado</h1>
        <p className="intro-description">Documento consultável sem login. Exibe apenas aliases públicos, sem e-mail, nome ou identificador de usuário.</p>
      </div>
      {error && <ErrorState message={error} onRetry={() => setReloadKey(value => value + 1)} />}
      {receipt === null && !error && <LoadingState label="Carregando comprovante…" />}
      {receipt && (
        <div className="receipt-layout">
          <article className="receipt-card">
            <div className="receipt-head">
              <div>
                <span className="eyebrow">Comprovante {receipt.code}</span>
                <h2>{receipt.item_title}</h2>
              </div>
              <Icon name="receipt" />
            </div>
            <LotImage src={receipt.item_image_url} alt={receipt.item_title} className="receipt-artwork" />
            <div className="receipt-grid">
              <div><span className="eyebrow">Valor final</span><strong>R$ {money(receipt.final_price)}</strong></div>
              <div><span className="eyebrow">Lote</span><strong>{receipt.lot_code}</strong></div>
              <div><span className="eyebrow">Arrematante</span><strong>{receipt.winner_alias}</strong></div>
              <div><span className="eyebrow">Leiloeiro</span><strong>{receipt.seller_alias}</strong></div>
              <div><span className="eyebrow">Emissão</span><strong>{dateTime(receipt.issued_at)}</strong></div>
              <div><span className="eyebrow">Lances</span><strong>{receipt.bid_count}</strong></div>
            </div>
            <div className="receipt-hash">
              <span className="eyebrow">Cabeça da auditoria</span>
              <code title={receipt.audit_head}>{shortHash(receipt.audit_head)}</code>
            </div>
            <p className="receipt-note">O comprovante é um snapshot imutável no banco. Ele não substitui a âncora externa contra rollback completo da base.</p>
          </article>
          <aside className="receipt-side">
            <section className="panel-card">
              <div className="panel-heading"><p className="eyebrow gold">Verificação</p><h2>Estado do documento</h2></div>
              {verification === null
                ? <p className="muted-copy">Verificação detalhada indisponível no momento.</p>
                : (
                  <ul className="check-list">
                    <li className={verification.receipt_valid ? 'ok' : 'fail'}><Icon name={verification.receipt_valid ? 'check' : 'alert'} /> Assinatura do comprovante</li>
                    <li className={verification.history_valid ? 'ok' : 'fail'}><Icon name={verification.history_valid ? 'check' : 'alert'} /> Histórico de lances</li>
                    <li className={verification.head_matches ? 'ok' : 'fail'}><Icon name={verification.head_matches ? 'check' : 'alert'} /> Cabeça da cadeia</li>
                    <li className={verification.anchor_status === 'ok' ? 'ok' : 'neutral'}><Icon name="shield" /> Âncora: {verification.anchor_status}</li>
                  </ul>
                )}
            </section>
            <section className="panel-card">
              <div className="panel-heading"><p className="eyebrow gold">Compartilhar</p><h2>Link público</h2></div>
              <div className="share-row">
                <input readOnly value={shareUrl} aria-label="Link público do comprovante" />
                <button className="primary-button" onClick={() => { void copyLink() }} disabled={shareUrl === ''}>{copied ? 'Copiado' : 'Copiar'}</button>
              </div>
              <p className="bid-notice">Qualquer pessoa com este link pode consultar o comprovante. Não há dados pessoais no conteúdo.</p>
            </section>
            <Link className="text-link" to="/">Voltar para a vitrine <span aria-hidden="true">→</span></Link>
          </aside>
        </div>
      )}
    </div>
  )
}
