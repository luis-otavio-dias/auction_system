import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchAudit } from '../../api/catalog'
import Icon from '../../components/Icon'
import { ErrorState, LoadingState } from '../../components/ui/States'
import type { AuditAnchorStatus, AuditReport } from '../../types/api'
import { errorMessage } from '../../utils/errors'
import { dateTime, money, shortHash } from '../../utils/format'

const FAILURE_LABELS: Record<string, string> = {
  SEQUENCE_GAP: 'Sequência descontínua',
  PREV_HASH_MISMATCH: 'Elo anterior divergente',
  CONTENT_HASH_MISMATCH: 'Conteúdo do lance alterado',
  CHAIN_HASH_MISMATCH: 'Assinatura da cadeia inválida',
  COUNT_MISMATCH: 'Contagem de lances divergente',
  HEAD_MISMATCH: 'Cabeça da cadeia divergente',
  ROLLBACK_DETECTED: 'Rollback detectado pela âncora',
}

const ANCHOR_LABELS: Record<AuditAnchorStatus, string> = {
  ok: 'Âncora externa compatível',
  behind: 'Âncora externa atrasada',
  rollback_detected: 'Rollback detectado pela âncora',
  unavailable: 'Âncora externa indisponível',
}

const GUARANTEES = [
  'A verificação é feita pelo backend e confirma a cadeia HMAC lance a lance.',
  'Alterações, inserções e remoções no banco são detectadas sem o segredo HMAC.',
  'A contagem de lances e a cabeça da cadeia são comparadas com o estado do lote.',
]

const LIMITATIONS = [
  'O visitante não reproduz o HMAC sozinho: a verificação é uma consulta ao backend.',
  'A âncora em arquivo no mesmo servidor não protege contra quem controla a infraestrutura.',
  'Um rollback completo do banco só é detectável quando o checkpoint externo confiável está disponível.',
]

export default function AuditPage() {
  const { id = '' } = useParams()
  const [report, setReport] = useState<AuditReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setReport(null)
      try {
        const result = await fetchAudit(id, controller.signal)
        if (!controller.signal.aborted) {
          setReport(result)
          setError(null)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          setError(errorMessage(cause, 'Não foi possível carregar a auditoria.'))
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [id, reloadKey])

  return (
    <div className="container page-section">
      <div className="room-breadcrumb">
        <Link to="/">Vitrine</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/lotes/${id}`}>Lote</Link>
        <span aria-hidden="true">/</span>
        <span>Auditoria</span>
      </div>
      <div className="page-heading">
        <p className="eyebrow gold">Auditoria pública</p>
        <h1>Integridade do histórico</h1>
        <p className="intro-description">Consulta aberta, sem login e sem dados pessoais. O resultado é calculado pelo backend a partir da cadeia de hashes dos lances.</p>
      </div>
      {error && <ErrorState message={error} onRetry={() => setReloadKey(value => value + 1)} />}
      {report === null && !error && <LoadingState label="Verificando a cadeia de lances…" />}
      {report && (
        <>
          <div className={report.valid ? 'audit-banner valid' : 'audit-banner invalid'} role="status">
            <Icon name={report.valid ? 'shield' : 'alert'} />
            <div>
              <strong>{report.valid ? 'Histórico íntegro' : 'Histórico adulterado'}</strong>
              <span>{report.valid ? 'Todos os elos da cadeia conferem com os hashes registrados.' : 'Foram encontradas divergências na cadeia de lances.'}</span>
            </div>
          </div>
          <div className="audit-grid">
            <div className="metric-card"><span>Cabeça da cadeia</span><code className="hash-value" title={report.head_hash}>{report.head_hash || '—'}</code></div>
            <div className="metric-card"><span>Lances verificados</span><strong>{report.bid_count}</strong></div>
            <div className="metric-card"><span>Primeira falha</span><strong>{report.first_invalid_sequence ?? '—'}</strong></div>
            <div className="metric-card"><span>Garantia adicional</span><strong>{ANCHOR_LABELS[report.anchor_status]}</strong></div>
          </div>
          {report.failures.length > 0 && (
            <section className="panel-card">
              <div className="panel-heading"><p className="eyebrow gold">Falhas</p><h2>Divergências detectadas</h2></div>
              <ul className="failure-list">
                {report.failures.map((failure, index) => (
                  <li key={`${failure.code}-${index}`}>
                    <span className="status-badge status-cancelled">{failure.code}</span>
                    <strong>{FAILURE_LABELS[failure.code] ?? 'Falha de integridade'}</strong>
                    <span>{failure.sequence !== null ? `Sequência ${failure.sequence}` : 'Sem sequência associada'}{failure.detail ? ` — ${failure.detail}` : ''}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="panel-card">
            <div className="panel-heading"><p className="eyebrow gold">Cadeia de lances</p><h2>Lances e hashes</h2></div>
            {report.bids.length === 0
              ? <p className="muted-copy">Nenhum lance registrado para este lote.</p>
              : (
                <div className="table-wrap">
                  <table className="data-table audit-table">
                    <thead><tr><th>Seq.</th><th>Valor</th><th>Alias</th><th>Data</th><th>Hash anterior</th><th>Hash do conteúdo</th><th>HMAC</th></tr></thead>
                    <tbody>
                      {report.bids.map(bid => (
                        <tr key={bid.sequence}>
                          <td>{bid.sequence}</td>
                          <td>R$ {money(bid.amount)}</td>
                          <td>{bid.bidder_alias}</td>
                          <td>{dateTime(bid.placed_at)}</td>
                          <td><code title={bid.prev_hash}>{shortHash(bid.prev_hash)}</code></td>
                          <td><code title={bid.content_hash}>{shortHash(bid.content_hash)}</code></td>
                          <td><code title={bid.hash}>{shortHash(bid.hash)}</code></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </section>
          <div className="guarantee-grid">
            <section className="panel-card">
              <div className="panel-heading"><p className="eyebrow gold">Garantias</p><h2>O que é verificado</h2></div>
              <ul className="plain-list">{(report.guarantees.length > 0 ? report.guarantees : GUARANTEES).map(item => <li key={item}>{item}</li>)}</ul>
            </section>
            <section className="panel-card">
              <div className="panel-heading"><p className="eyebrow gold">Limitações</p><h2>O que não é garantido</h2></div>
              <ul className="plain-list">{(report.limitations.length > 0 ? report.limitations : LIMITATIONS).map(item => <li key={item}>{item}</li>)}</ul>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
