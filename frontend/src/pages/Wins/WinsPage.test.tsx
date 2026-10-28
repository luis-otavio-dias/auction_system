import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import WinsPage from './WinsPage'
import { installFetch, jsonReply } from '../../test/apiMock'

describe('meus arremates', () => {
  it('usa share_url, issued_at e lot_id e lista os lotes com lance', async () => {
    installFetch(url => {
      if (url.endsWith('/api/me/wins')) {
        return jsonReply([{
          lot_id: 'lot-2',
          lot_code: 'L-2',
          title: 'Nighthawks',
          final_price: '525.00',
          settled_at: '2026-10-27T19:48:23Z',
          issued_at: '2026-10-27T19:48:24Z',
          receipt_token: 'token-2',
          share_url: 'https://front.example/comprovantes/token-2',
        }])
      }
      if (url.endsWith('/api/me/bids?page=1')) {
        return jsonReply({
          count: 1,
          next: null,
          previous: null,
          results: [{
            lot_id: 'lot-3',
            lot_code: 'L-3',
            lot_title: 'Paisagem',
            sequence: 2,
            amount: '550.00',
            placed_at: '2026-10-27T19:40:00Z',
            is_mine: true,
          }],
        })
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    render(
      <MemoryRouter>
        <WinsPage />
      </MemoryRouter>,
    )

    const receipt = await screen.findByRole('link', { name: /Abrir comprovante/i })
    expect(receipt).toHaveAttribute('href', 'https://front.example/comprovantes/token-2')
    expect(screen.getByText(/Emitido em/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /L-3/ })).toHaveAttribute('href', '/lotes/lot-3')
    expect(screen.getByText('Paisagem')).toBeInTheDocument()
    expect(screen.getByText(/R\$ 550,00/)).toBeInTheDocument()
  })
})
