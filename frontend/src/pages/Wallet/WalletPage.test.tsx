import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AuthContext } from '../../context/auth-context'
import type { AuthContextValue } from '../../context/auth-context'
import ToastProvider from '../../context/ToastProvider'
import WalletPage from './WalletPage'
import { installFetch, jsonReply } from '../../test/apiMock'
import { sellerUser } from '../../test/fixtures'

const authValue: AuthContextValue = {
  user: sellerUser,
  loading: false,
  login: async () => undefined,
  register: async () => undefined,
  logout: async () => undefined,
  refreshUser: async () => undefined,
}

const walletPayload = {
  id: 'wallet-seller',
  balance: '900.00',
  committed: '0.00',
  available: '900.00',
  updated_at: '2026-10-27T19:00:00.000Z',
}

const transactionPayload = {
  id: 'tx-1',
  type: 'SETTLEMENT_CREDIT',
  amount: '1050.00',
  balance_after: '900.00',
  committed_after: '0.00',
  reference_kind: 'LOT',
  reference_id: 'lot-9',
  description: 'Crédito de venda do lote L-9',
  created_at: '2026-10-27T19:48:23.000Z',
}

function renderWallet() {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={authValue}>
        <ToastProvider>
          <WalletPage />
        </ToastProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe('carteira do leiloeiro', () => {
  it('exibe saldo e extrato com créditos de liquidação quando o backend libera', async () => {
    installFetch(url => {
      if (url.endsWith('/api/wallet/transactions?page=1')) {
        return jsonReply({ count: 1, next: null, previous: null, results: [transactionPayload] })
      }
      if (url.endsWith('/api/wallet')) {
        return jsonReply(walletPayload)
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    renderWallet()

    expect(await screen.findByText('Crédito de venda')).toBeInTheDocument()
    expect(screen.getByText(/Depósitos simulados são exclusivos de licitantes/i)).toBeInTheDocument()
    expect(screen.getAllByText(/R\$ 1\.050,00/).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Depositar' })).not.toBeInTheDocument()
  })

  it('mantém a carteira e a orientação quando apenas o extrato falha', async () => {
    installFetch(url => {
      if (url.endsWith('/api/wallet/transactions?page=1')) {
        return jsonReply({ detail: 'Apenas licitantes podem usar esta operação.' }, 403)
      }
      if (url.endsWith('/api/wallet')) {
        return jsonReply(walletPayload)
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    renderWallet()

    expect(await screen.findByText('Saldo total')).toBeInTheDocument()
    expect(screen.getAllByText(/R\$ 900,00/).length).toBeGreaterThan(0)
    expect(screen.getByText(/extrato detalhado do leiloeiro será exibido aqui/i)).toBeInTheDocument()
    expect(screen.getByText(/Depósitos simulados são exclusivos de licitantes/i)).toBeInTheDocument()
    expect(screen.queryByText('Não foi possível carregar o extrato.')).not.toBeInTheDocument()
  })
})
