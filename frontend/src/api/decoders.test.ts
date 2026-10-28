import { describe, expect, it } from 'vitest'
import {
  decodeAuditReport,
  decodeLotDetail,
  decodeLotEvent,
  decodeMyBid,
  decodeNotification,
  decodePaginated,
  decodeSellerSummary,
  decodeWin,
} from './decoders'
import type { JsonValue } from './json'

const lotDetailPayload: JsonValue = {
  id: 'lot-1',
  code: 'L-0000000001',
  status: 'live',
  title: 'Noite sobre o Sena',
  description: 'Óleo sobre tela.',
  image_url: 'https://example.test/lot.jpg',
  source: 'artic',
  external_id: '12345',
  source_url: 'https://example.test/item',
  category: 'Pintura',
  attributes: { artista: 'Exemplo' },
  starting_bid: '500.00',
  min_increment: '25.00',
  current_bid: '525.00',
  minimum_bid: '550.00',
  starts_at: '2026-10-27T10:00:00Z',
  ends_at: '2026-10-28T10:00:00Z',
  original_ends_at: '2026-10-28T10:00:00Z',
  extension_count: 0,
  bids_count: 2,
  state_version: 3,
  seller_alias: 'Leiloeiro-ABC123',
  my_position: {
    is_leading: false,
    status: 'outbid',
    last_amount: '500.00',
    rank: 2,
  },
  server_time: '2026-10-27T12:00:00Z',
}

describe('decoders do contrato real', () => {
  it('lê my_position com last_amount do backend', () => {
    const lot = decodeLotDetail(lotDetailPayload)
    expect(lot.my_position).toEqual({
      is_leading: false,
      status: 'outbid',
      last_amount: '500.00',
      rank: 2,
    })
  })

  it('lê o resumo do leiloeiro com resultado por lote, sem arremate e bloqueios', () => {
    const summary = decodeSellerSummary({
      total_received: '525.00',
      settled_count: 1,
      unsold_count: 1,
      results_by_lot: [{
        lot_id: 'lot-9',
        code: 'L-1',
        title: 'Nighthawks',
        final_price: '525.00',
        winner_alias: 'Cliente Dois',
        settled_at: '2026-10-27T19:48:23Z',
      }],
      unsold_lots: [{ lot_id: 'lot-10', code: 'L-2', title: 'Sem lance', settled_at: '2026-10-27T20:00:00Z' }],
      blocked_lots: [{ lot_id: 'lot-11', code: 'L-3', title: 'Bloqueado', settlement_error: 'Cadeia divergente.' }],
    })
    expect(summary).toEqual({
      total_received: '525.00',
      settled_count: 1,
      unsold_count: 1,
      results: [{
        lot_id: 'lot-9',
        code: 'L-1',
        title: 'Nighthawks',
        final_price: '525.00',
        winner_alias: 'Cliente Dois',
        settled_at: '2026-10-27T19:48:23Z',
      }],
      unsold_lots: [{ lot_id: 'lot-10', code: 'L-2', title: 'Sem lance', ends_at: '2026-10-27T20:00:00Z' }],
      blocked_lots: [{ lot_id: 'lot-11', code: 'L-3', title: 'Bloqueado', settlement_error: 'Cadeia divergente.' }],
    })
  })

  it('lê arremates com lot_id, issued_at e share_url', () => {
    const wins = decodePaginated(
      [{
        lot_id: 'lot-2',
        lot_code: 'L-2',
        title: 'Nighthawks',
        final_price: '525.00',
        settled_at: '2026-10-27T19:48:23Z',
        issued_at: '2026-10-27T19:48:24Z',
        receipt_token: 'token-2',
        share_url: 'https://front.example/comprovantes/token-2',
      }],
      'meus arremates',
      decodeWin,
    )
    expect(wins.results[0]).toEqual({
      lot_id: 'lot-2',
      lot_code: 'L-2',
      title: 'Nighthawks',
      final_price: '525.00',
      settled_at: '2026-10-27T19:48:23Z',
      issued_at: '2026-10-27T19:48:24Z',
      receipt_token: 'token-2',
      share_url: 'https://front.example/comprovantes/token-2',
    })
  })

  it('lê meus lances com lot_id, lot_code e lot_title', () => {
    const bid = decodeMyBid({
      lot_id: 'lot-2',
      lot_code: 'L-2',
      lot_title: 'Nighthawks',
      sequence: 4,
      amount: '550.00',
      placed_at: '2026-10-27T19:40:00Z',
      is_mine: true,
    })
    expect(bid).toEqual({
      lot_id: 'lot-2',
      lot_code: 'L-2',
      lot_title: 'Nighthawks',
      sequence: 4,
      amount: '550.00',
      placed_at: '2026-10-27T19:40:00Z',
      is_mine: true,
    })
  })

  it('normaliza limitations em texto único da auditoria', () => {
    const audit = decodeAuditReport({
      valid: true,
      head_hash: 'a'.repeat(64),
      bid_count: 1,
      first_invalid_sequence: null,
      anchor_status: 'unavailable',
      failures: [],
      bids: [],
      limitations: 'Verificação HMAC feita pelo backend.',
    })
    expect(audit.limitations).toEqual(['Verificação HMAC feita pelo backend.'])
    expect(audit.guarantees).toEqual([])
  })

  it('lê o snapshot achatado do WebSocket', () => {
    const event = decodeLotEvent({
      event: 'lot.snapshot',
      lot_id: 'lot-1',
      code: 'L-0000000001',
      title: 'Noite sobre o Sena',
      status: 'live',
      current_bid: '525.00',
      minimum_bid: '550.00',
      ends_at: '2026-10-28T10:00:00Z',
      bids_count: 2,
      state_version: 3,
      server_time: '2026-10-27T12:00:00Z',
      my_position: {
        is_leading: true,
        status: 'leading',
        last_amount: '525.00',
        rank: 1,
      },
    })
    expect(event).toEqual({
      type: 'lot.snapshot',
      snapshot: {
        lot_id: 'lot-1',
        code: 'L-0000000001',
        title: 'Noite sobre o Sena',
        status: 'live',
        current_bid: '525.00',
        minimum_bid: '550.00',
        ends_at: '2026-10-28T10:00:00Z',
        bids_count: 2,
        state_version: 3,
        server_time: '2026-10-27T12:00:00Z',
        my_position: {
          is_leading: true,
          status: 'leading',
          last_amount: '525.00',
          rank: 1,
        },
      },
    })
  })

  it('mantém fallback quando a notificação não traz lot_id', () => {
    const notification = decodeNotification({
      event: 'user.outbid',
      lot_code: 'L-0000000001',
      state_version: 4,
    })
    expect(notification?.kind).toBe('outbid')
    expect(notification?.lot_id).toBeNull()
    expect(notification?.lot_href).toBeNull()
    expect(notification?.href).toBeNull()
    expect(notification?.message).toContain('L-0000000001')
  })

  it('usa lot_id da notificação para link direto ao lote e ao comprovante', () => {
    const notification = decodeNotification({
      event: 'user.won',
      lot_id: 'lot-7',
      lot_code: 'L-0000000007',
      final_price: '900.00',
      receipt_token: 'token-7',
      state_version: 8,
    })
    expect(notification?.lot_id).toBe('lot-7')
    expect(notification?.lot_href).toBe('/lotes/lot-7')
    expect(notification?.receipt_href).toBe('/comprovantes/token-7')
    expect(notification?.href).toBe('/comprovantes/token-7')
  })
})
