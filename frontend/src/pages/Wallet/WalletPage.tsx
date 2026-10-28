import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { deposit, fetchTransactions, fetchWallet } from '../../api/wallet'
import { ErrorState, LoadingState } from '../../components/ui/States'
import PaginationControls from '../../components/ui/PaginationControls'
import { useAuth } from '../../context/auth-context'
import { useToast } from '../../context/toast-context'
import type { Paginated, Wallet, WalletTransaction, WalletTransactionType } from '../../types/api'
import { errorMessage } from '../../utils/errors'
import { dateTime, money, parseAmount } from '../../utils/format'
import { createClientId } from '../../utils/id'

const TRANSACTION_LABELS: Record<WalletTransactionType, string> = {
  DEPOSIT: 'Depósito',
  BID_HOLD: 'Reserva de lance',
  BID_RELEASE: 'Liberação de reserva',
  SETTLEMENT_DEBIT: 'Débito de arremate',
  SETTLEMENT_CREDIT: 'Crédito de venda',
  CANCELLATION_RELEASE: 'Liberação por cancelamento',
  ADJUSTMENT_CREDIT: 'Ajuste de crédito',
  ADJUSTMENT_DEBIT: 'Ajuste de débito',
  UNKNOWN: 'Lançamento',
}

const CREDIT_TYPES: readonly WalletTransactionType[] = ['DEPOSIT', 'SETTLEMENT_CREDIT', 'ADJUSTMENT_CREDIT']
const DEBIT_TYPES: readonly WalletTransactionType[] = ['SETTLEMENT_DEBIT', 'ADJUSTMENT_DEBIT']

export default function WalletPage() {
  const { showToast } = useToast()
  const { user } = useAuth()
  const isSeller = user?.role === 'SELLER'
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [transactions, setTransactions] = useState<Paginated<WalletTransaction> | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [walletError, setWalletError] = useState<string | null>(null)
  const [transactionsError, setTransactionsError] = useState<string | null>(null)
  const [transactionsBlocked, setTransactionsBlocked] = useState(false)
  const [depositAmount, setDepositAmount] = useState('')
  const [depositError, setDepositError] = useState<string | null>(null)
  const [depositing, setDepositing] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const loadWallet = async () => {
      try {
        const nextWallet = await fetchWallet()
        if (!controller.signal.aborted) {
          setWallet(nextWallet)
          setWalletError(null)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          setWalletError(errorMessage(cause, 'Não foi possível carregar a carteira.'))
        }
      }
    }
    void loadWallet()
    return () => controller.abort()
  }, [reloadKey])

  useEffect(() => {
    const controller = new AbortController()
    const loadTransactions = async () => {
      setLoading(true)
      try {
        const result = await fetchTransactions(page)
        if (!controller.signal.aborted) {
          setTransactions(result)
          setTransactionsError(null)
          setTransactionsBlocked(false)
        }
      } catch (cause) {
        if (!controller.signal.aborted && cause instanceof Error) {
          if (isSeller && cause instanceof ApiError && cause.status === 403) {
            setTransactionsError(null)
            setTransactionsBlocked(true)
          } else {
            setTransactionsError(errorMessage(cause, 'Não foi possível carregar o extrato.'))
          }
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }
    void loadTransactions()
    return () => controller.abort()
  }, [page, reloadKey, isSeller])

  const submitDeposit = async (event: FormEvent) => {
    event.preventDefault()
    const parsed = parseAmount(depositAmount)
    if (parsed === null || parsed <= 0) {
      setDepositError('Informe um valor de depósito maior que zero.')
      return
    }
    setDepositing(true)
    setDepositError(null)
    try {
      await deposit(parsed.toFixed(2), createClientId())
      setDepositAmount('')
      setPage(1)
      setReloadKey(value => value + 1)
      showToast(`Depósito simulado de R$ ${money(parsed)} concluído.`, 'Carteira atualizada')
    } catch (cause) {
      if (cause instanceof ApiError) {
        setDepositError(cause.detail || 'Não foi possível concluir o depósito.')
      } else if (cause instanceof Error) {
        setDepositError(errorMessage(cause, 'Não foi possível concluir o depósito.'))
      }
    } finally {
      setDepositing(false)
    }
  }

  const rows = useMemo(() => transactions?.results ?? [], [transactions])

  return (
    <div className="container page-section">
      <div className="page-heading">
        <p className="eyebrow gold">{isSeller ? 'Carteira do leiloeiro' : 'Carteira do licitante'}</p>
        <h1>Saldo e compromissos</h1>
        <p className="intro-description">
          {isSeller
            ? 'Acompanhe o saldo das vendas liquidadas e os créditos de cada arremate.'
            : 'O saldo comprometido fica reservado enquanto seus lances lideram. Apenas o arremate é debitado definitivamente.'}
        </p>
      </div>
      {walletError && !wallet && <ErrorState message={walletError} onRetry={() => setReloadKey(value => value + 1)} />}
      {!wallet && !walletError && <LoadingState label="Carregando carteira…" />}
      {wallet && (
        <div className="wallet-grid">
          <div className="metric-card"><span>Saldo total</span><strong>R$ {money(wallet.balance)}</strong></div>
          <div className="metric-card"><span>Comprometido</span><strong>R$ {money(wallet.committed)}</strong></div>
          <div className="metric-card available"><span>{isSeller ? 'Disponível' : 'Disponível para lances'}</span><strong>R$ {money(wallet.available)}</strong></div>
        </div>
      )}
      {isSeller && (
        <section className="panel-card">
          <div className="panel-heading"><p className="eyebrow gold">Orientação</p><h2>Conta de leiloeiro</h2></div>
          <p className="muted-copy">Depósitos simulados são exclusivos de licitantes. Os créditos de liquidação de cada lote vendido aparecem no extrato assim que o backend processa o arremate.</p>
          <p className="bid-notice">O total recebido e o resultado por lote também estão disponíveis no painel do leiloeiro. <Link className="inline-link" to="/painel">Abrir painel</Link></p>
        </section>
      )}
      <div className="panel-grid">
        <section className="panel-card">
          <div className="panel-heading">
            <p className="eyebrow gold">{isSeller ? 'Vendas' : 'Depósito simulado'}</p>
            <h2>{isSeller ? 'Créditos de liquidação' : 'Adicionar saldo'}</h2>
          </div>
          {isSeller
            ? (
              <p className="muted-copy">Cada lote liquidado credita o valor final nesta carteira e gera um lançamento do tipo <strong>Crédito de venda</strong> no extrato.</p>
            )
            : (
              <form onSubmit={event => { void submitDeposit(event) }}>
                <label htmlFor="deposit-amount">Valor do depósito</label>
                <div className="bid-input">
                  <span>R$</span>
                  <input id="deposit-amount" inputMode="decimal" placeholder="1.000,00" value={depositAmount} onChange={event => { setDepositAmount(event.target.value); setDepositError(null) }} />
                </div>
                <div className="quick-amounts">
                  {['500', '1000', '5000'].map(value => <button type="button" key={value} className="quick-bid" onClick={() => setDepositAmount(value)}>+ R$ {money(value)}</button>)}
                </div>
                {depositError && <p className="bid-error" role="alert">{depositError}</p>}
                <button className="primary-button confirm-bid" type="submit" disabled={depositing}>{depositing ? 'Processando…' : 'Depositar'}</button>
                <p className="bid-notice">Depósito de demonstração, sem cobrança real. A operação é registrada no extrato.</p>
              </form>
            )}
        </section>
        <section className="panel-card panel-wide">
          <div className="panel-heading"><p className="eyebrow gold">Movimentações</p><h2>Extrato</h2></div>
          {loading && rows.length === 0 && <LoadingState label="Carregando extrato…" />}
          {!loading && transactionsBlocked && rows.length === 0 && (
            <p className="muted-copy" role="status">O extrato detalhado do leiloeiro será exibido aqui quando o backend liberar o acesso. Enquanto isso, consulte o resultado por lote no painel.</p>
          )}
          {!loading && !transactionsBlocked && transactionsError && rows.length === 0 && <ErrorState message={transactionsError} onRetry={() => setReloadKey(value => value + 1)} />}
          {!loading && !transactionsBlocked && !transactionsError && rows.length === 0 && <p className="muted-copy">Nenhuma movimentação registrada.</p>}
          {rows.length > 0 && (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Data</th><th>Tipo</th><th>Valor</th><th>Saldo após</th><th>Comprometido</th></tr></thead>
                <tbody>
                  {rows.map(item => {
                    const sign = CREDIT_TYPES.includes(item.type) ? '+' : DEBIT_TYPES.includes(item.type) ? '−' : '·'
                    return (
                      <tr key={item.id}>
                        <td>{dateTime(item.created_at)}</td>
                        <td>{TRANSACTION_LABELS[item.type]}{item.description && <span className="cell-note">{item.description}</span>}</td>
                        <td className={CREDIT_TYPES.includes(item.type) ? 'amount-credit' : DEBIT_TYPES.includes(item.type) ? 'amount-debit' : ''}>{sign} R$ {money(item.amount)}</td>
                        <td>R$ {money(item.balance_after)}</td>
                        <td>R$ {money(item.committed_after)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls
            page={page}
            hasNext={transactions?.next !== null && transactions?.next !== undefined}
            hasPrevious={transactions?.previous !== null && transactions?.previous !== undefined}
            onNext={() => setPage(current => current + 1)}
            onPrevious={() => setPage(current => Math.max(1, current - 1))}
          />
        </section>
      </div>
    </div>
  )
}
