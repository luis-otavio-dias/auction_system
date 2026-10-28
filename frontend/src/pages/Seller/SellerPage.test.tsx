import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ToastProvider from '../../context/ToastProvider'
import SellerPage from './SellerPage'
import { installFetch, jsonReply } from '../../test/apiMock'

describe('painel do leiloeiro', () => {
  it('exibe resultado por lote, lotes sem arremate e bloqueios do resumo', async () => {
    installFetch(url => {
      if (url.endsWith('/api/seller/summary')) {
        return jsonReply({
          total_received: '1050.00',
          settled_count: 1,
          unsold_count: 1,
          results: [{
            lot_id: 'lot-vendido',
            code: 'L-VENDIDO',
            title: 'Nighthawks',
            final_price: '1050.00',
            winner_alias: 'Cliente Dois',
            settled_at: '2026-10-27T19:48:23Z',
          }],
          unsold_lots: [{
            lot_id: 'lot-sem-vencedor',
            code: 'L-SEM-VENCEDOR',
            title: 'Paisagem sem lance',
            ends_at: '2026-10-27T20:00:00Z',
          }],
          blocked_lots: [{
            lot_id: 'lot-bloqueado',
            code: 'L-BLOQUEADO',
            title: 'Obra bloqueada',
            settlement_error: 'Cadeia divergente.',
          }],
        })
      }
      if (url.includes('/api/seller/lots')) {
        return jsonReply({ count: 0, next: null, previous: null, results: [] })
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    render(
      <MemoryRouter>
        <ToastProvider>
          <SellerPage />
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'L-VENDIDO' })).toBeInTheDocument()
    expect(screen.getByText('Cliente Dois')).toBeInTheDocument()
    expect(screen.getAllByText(/R\$ 1\.050,00/).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'L-SEM-VENCEDOR' })).toBeInTheDocument()
    expect(screen.getByText('L-BLOQUEADO')).toBeInTheDocument()
    expect(screen.getByText('Cadeia divergente.')).toBeInTheDocument()
  })
})
