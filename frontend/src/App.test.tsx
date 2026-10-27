import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { getLots } from './services/auctionService'
import type { Lot } from './types/auction'

vi.mock('./services/auctionService', () => ({
  getCategories: vi.fn(() => ['Relógios']),
  getLots: vi.fn(() => []),
}))

const sampleLot: Lot = {
  id: '1',
  title: 'Relógio de Bolso Vintage',
  description: 'Relógio de bolso em aço, com mostrador branco.',
  provenance: 'Coleção particular',
  status: 'Reserva Atingida',
  image: '',
  alt: 'Relógio de bolso vintage',
  bid: 1500,
  increment: 100,
  seconds: 3600,
  estimate: 'R$ 2.000 – R$ 3.000',
  category: 'Relógios',
}

describe('App Integration', () => {
  beforeEach(() => {
    vi.mocked(getLots).mockReturnValue([sampleLot])
  })

  it('renders the catalog from the service and shows the scheduled empty state', async () => {
    const user = userEvent.setup()

    render(<App />)

    expect(screen.getByRole('heading', { name: /explore os lotes/i })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: sampleLot.title })).toBeInTheDocument()
    expect(screen.getByText('Lote 001')).toBeInTheDocument()
    expect(screen.getByText('1.500,00')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /programados/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /nenhum lote programado/i })).toBeInTheDocument()
    })
  })
})
