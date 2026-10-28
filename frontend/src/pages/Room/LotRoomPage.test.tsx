import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../../context/auth-context'
import type { AuthContextValue } from '../../context/auth-context'
import ToastProvider from '../../context/ToastProvider'
import LotRoomPage from './LotRoomPage'
import { installFetch, jsonReply, MockWebSocket, requestBody } from '../../test/apiMock'
import { bidderUser, lotDetail } from '../../test/fixtures'

const authValue: AuthContextValue = {
  user: bidderUser,
  loading: false,
  login: vi.fn(async () => undefined),
  register: vi.fn(async () => undefined),
  logout: vi.fn(async () => undefined),
  refreshUser: vi.fn(async () => undefined),
}

function renderRoom() {
  return render(
    <MemoryRouter initialEntries={['/lotes/lot-1']}>
      <AuthContext.Provider value={authValue}>
        <ToastProvider>
          <Routes>
            <Route path="/lotes/:id" element={<LotRoomPage />} />
          </Routes>
        </ToastProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

const bidHistory = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      sequence: 1,
      amount: '500.00',
      bidder_alias: 'Cliente Dois',
      placed_at: '2026-10-27T12:00:00.000Z',
      is_mine: false,
    },
  ],
}

describe('sala do lote', () => {
  it('mapeia o erro de valor exato e envia client_bid_id gerado antes do request', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('WebSocket', MockWebSocket)
    const calls = installFetch((url, init) => {
      if (url.endsWith('/api/auth/ws-ticket')) {
        return jsonReply({ ticket: 'ticket-teste' })
      }
      if (url.includes('/api/lots/lot-1/bids') && init.method === 'POST') {
        return jsonReply({ code: 'BID_AMOUNT_MISMATCH', detail: 'valor divergente' }, 422)
      }
      if (url.includes('/api/lots/lot-1/bids')) {
        return jsonReply(bidHistory)
      }
      if (url.endsWith('/api/lots/lot-1')) {
        return jsonReply(lotDetail())
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    renderRoom()

    expect(await screen.findByRole('heading', { name: 'Noite sobre o Sena' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Valor do lance'), '500')
    await user.click(screen.getByRole('button', { name: 'Confirmar lance' }))

    await waitFor(() => {
      expect(calls.some(call => call.method === 'POST')).toBe(true)
    })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/valor precisa ser exatamente/i)
    const post = calls.find(call => call.method === 'POST' && call.url.endsWith('/api/lots/lot-1/bids'))
    expect(post).toBeDefined()
    const body = requestBody(post ?? { url: '', method: '', body: null, credentials: null })
    expect(body.amount).toBe('500.00')
    expect(typeof body.client_bid_id).toBe('string')
    expect(String(body.client_bid_id)).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })

  it('exibe available e minimum_bid no erro INSUFFICIENT_FUNDS', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('WebSocket', MockWebSocket)
    installFetch((url, init) => {
      if (url.endsWith('/api/auth/ws-ticket')) {
        return jsonReply({ ticket: 'ticket-teste' })
      }
      if (url.includes('/api/lots/lot-1/bids') && init.method === 'POST') {
        return jsonReply({
          code: 'INSUFFICIENT_FUNDS',
          detail: 'Saldo disponível insuficiente.',
          available: '50.00',
          minimum_bid: '525.00',
        }, 409)
      }
      if (url.includes('/api/lots/lot-1/bids')) {
        return jsonReply(bidHistory)
      }
      if (url.endsWith('/api/lots/lot-1')) {
        return jsonReply(lotDetail())
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    renderRoom()

    expect(await screen.findByRole('heading', { name: 'Noite sobre o Sena' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Valor do lance'), '525')
    await user.click(screen.getByRole('button', { name: 'Confirmar lance' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/saldo disponível insuficiente/i)
    expect(screen.getByText(/Disponível: R\$ 50,00/)).toBeInTheDocument()
    expect(screen.getByText(/Lance mínimo: R\$ 525,00/)).toBeInTheDocument()
  })

  it('reutiliza o client_bid_id quando a primeira tentativa falha por rede', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('WebSocket', MockWebSocket)
    let posts = 0
    const calls = installFetch((url, init) => {
      if (url.endsWith('/api/auth/ws-ticket')) {
        return jsonReply({ ticket: 'ticket-teste' })
      }
      if (url.includes('/api/lots/lot-1/bids') && init.method === 'POST') {
        posts += 1
        if (posts === 1) {
          throw new Error('rede indisponível')
        }
        return jsonReply({ state_version: 11, detail: 'lance aceito' })
      }
      if (url.includes('/api/lots/lot-1/bids')) {
        return jsonReply(bidHistory)
      }
      if (url.endsWith('/api/lots/lot-1')) {
        return jsonReply(lotDetail())
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    renderRoom()

    expect(await screen.findByRole('heading', { name: 'Noite sobre o Sena' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Valor do lance'), '525')
    await user.click(screen.getByRole('button', { name: 'Confirmar lance' }))
    expect(await screen.findByText(/não foi possível conectar ao servidor/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Confirmar lance' }))
    await waitFor(() => {
      expect(calls.filter(call => call.method === 'POST' && call.url.endsWith('/api/lots/lot-1/bids'))).toHaveLength(2)
    })

    const postCalls = calls.filter(call => call.method === 'POST' && call.url.endsWith('/api/lots/lot-1/bids'))
    const first = requestBody(postCalls[0] ?? { url: '', method: '', body: null, credentials: null })
    const second = requestBody(postCalls[1] ?? { url: '', method: '', body: null, credentials: null })
    expect(second.client_bid_id).toBe(first.client_bid_id)
  })
})
