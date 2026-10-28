import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import { installFetch, jsonReply, queryParam } from './test/apiMock'
import { lotDetail, lotSummary } from './test/fixtures'

describe('vitrine integrada', () => {
  it('carrega lotes da API, exibe contagem e alterna para programados', async () => {
    const user = userEvent.setup()
    window.history.pushState({}, '', '/')
    installFetch(url => {
      if (url.endsWith('/api/auth/me/')) {
        return jsonReply({ detail: 'anônimo' }, 401)
      }
      if (url.endsWith('/api/auth/refresh/')) {
        return jsonReply({ detail: 'sem sessão' }, 401)
      }
      if (url.endsWith('/api/lots/lot-1')) {
        return jsonReply(lotDetail())
      }
      if (url.includes('/api/lots?')) {
        const tab = queryParam(url, 'tab')
        if (tab === 'live') {
          return jsonReply({ count: 1, next: null, previous: null, results: [lotSummary()] })
        }
        return jsonReply({ count: 0, next: null, previous: null, results: [] })
      }
      return jsonReply({ detail: 'não encontrado' }, 404)
    })

    render(<App />)

    expect(screen.getByRole('heading', { name: /explore os lotes/i })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Noite sobre o Sena' })).toBeInTheDocument()
    expect(screen.getByText('Lote L-000000001')).toBeInTheDocument()
    expect(screen.getAllByText(/R\$ 500,00/).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /entrar na sala/i })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /programados/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /nenhum lote programado/i })).toBeInTheDocument()
    })
  })
})
