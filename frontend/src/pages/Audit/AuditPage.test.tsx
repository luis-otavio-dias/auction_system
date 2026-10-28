import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../../App'
import type { JsonObject } from '../../api/json'
import { installFetch, jsonReply } from '../../test/apiMock'

const validAudit = {
  valid: true,
  head_hash: 'a'.repeat(64),
  bid_count: 2,
  first_invalid_sequence: null,
  anchor_status: 'ok',
  failures: [],
  bids: [
    { sequence: 1, amount: '500.00', bidder_alias: 'Cliente Um', placed_at: '2026-10-27T12:00:00.000Z', prev_hash: '0'.repeat(64), content_hash: 'b'.repeat(64), hash: 'c'.repeat(64) },
    { sequence: 2, amount: '525.00', bidder_alias: 'Cliente Dois', placed_at: '2026-10-27T12:01:00.000Z', prev_hash: 'c'.repeat(64), content_hash: 'd'.repeat(64), hash: 'e'.repeat(64) },
  ],
  guarantees: [],
  limitations: [],
}

function installAuditFetch(audit: JsonObject) {
  window.history.pushState({}, '', '/lotes/lot-1/auditoria')
  return installFetch(url => {
    if (url.endsWith('/api/auth/me/')) {
      return jsonReply({ detail: 'anônimo' }, 401)
    }
    if (url.endsWith('/api/auth/refresh/')) {
      return jsonReply({ detail: 'sem sessão' }, 401)
    }
    if (url.endsWith('/api/lots/lot-1/audit')) {
      return jsonReply(audit)
    }
    return jsonReply({ detail: 'não encontrado' }, 404)
  })
}

describe('auditoria pública', () => {
  it('exibe histórico íntegro sem login e sem PII', async () => {
    installAuditFetch(validAudit)
    render(<App />)

    expect(await screen.findByRole('heading', { name: /integridade do histórico/i })).toBeInTheDocument()
    expect(await screen.findByText('Histórico íntegro')).toBeInTheDocument()
    expect(screen.getByText('Âncora externa compatível')).toBeInTheDocument()
    expect(screen.getByText('Cliente Um')).toBeInTheDocument()
    expect(screen.getByText('Cliente Dois')).toBeInTheDocument()
    expect(screen.queryByText('cliente1@demo.com')).not.toBeInTheDocument()
    expect(screen.getByText(/o visitante não reproduz o hmac sozinho/i)).toBeInTheDocument()
  })

  it('destaca adulteração e a primeira sequência inválida', async () => {
    installAuditFetch({
      ...validAudit,
      valid: false,
      first_invalid_sequence: 2,
      anchor_status: 'rollback_detected',
      failures: [{ code: 'CONTENT_HASH_MISMATCH', sequence: 2, detail: 'hash recalculado diverge' }],
    })
    render(<App />)

    expect(await screen.findByText('Histórico adulterado')).toBeInTheDocument()
    expect(screen.getByText('Conteúdo do lance alterado')).toBeInTheDocument()
    expect(screen.getByText(/sequência 2/i)).toBeInTheDocument()
    expect(screen.getByText('Rollback detectado pela âncora')).toBeInTheDocument()
  })
})
