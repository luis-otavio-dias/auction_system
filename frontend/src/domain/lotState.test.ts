import { describe, expect, it } from 'vitest'
import { evaluateEvent, evaluateSnapshot, mergeLotEvent, mergeLotSnapshot } from './lotState'
import { lotDetail } from '../test/fixtures'

describe('controle de state_version', () => {
  it('descarta resposta HTTP antiga que chega depois de um evento novo', () => {
    let version = 10
    const event = evaluateEvent(version, 11)
    expect(event.accept).toBe(true)
    version = 11

    const delayedPolling = evaluateSnapshot(version, 10)
    expect(delayedPolling.accept).toBe(false)
    expect(delayedPolling.stale).toBe(true)
    expect(version).toBe(11)
  })

  it('detecta salto de versão e exige snapshot em vez de aplicar evento parcial', () => {
    const gap = evaluateEvent(10, 13)
    expect(gap.accept).toBe(false)
    expect(gap.gap).toBe(true)

    const snapshot = evaluateSnapshot(10, 13)
    expect(snapshot.accept).toBe(true)
    expect(snapshot.gap).toBe(true)
  })

  it('ignora versão igual ou menor como idempotente/atrasada', () => {
    expect(evaluateEvent(11, 11).accept).toBe(false)
    expect(evaluateEvent(11, 9).accept).toBe(false)
    expect(evaluateSnapshot(11, 11).accept).toBe(false)
    expect(evaluateSnapshot(11, 9).accept).toBe(false)
  })

  it('aplica lance e encerramento preservando a maior versão', () => {
    const lot = lotDetail({ state_version: 10 })
    const afterBid = mergeLotEvent(lot, {
      type: 'bid.accepted',
      state_version: 11,
      current_bid: '550.00',
      minimum_bid: '575.00',
      bids_count: 2,
      ends_at: '2099-10-27T18:02:00.000Z',
      bidder_alias: 'Cliente Dois',
      sequence: 2,
    })
    expect(afterBid.current_bid).toBe('550.00')
    expect(afterBid.bids_count).toBe(2)
    expect(afterBid.state_version).toBe(11)

    const closed = mergeLotEvent(afterBid, {
      type: 'lot.closed',
      state_version: 12,
      final_price: '550.00',
      winner_alias: 'Cliente Dois',
      receipt_token: 'token-1',
    })
    expect(closed.status).toBe('ended')
    expect(closed.state_version).toBe(12)
  })

  it('mescla o snapshot achatado preservando dados completos do detalhe', () => {
    const lot = lotDetail({ state_version: 10, my_position: { is_leading: false, status: 'outbid', last_amount: '500.00', rank: 2 } })
    const merged = mergeLotSnapshot(lot, {
      lot_id: lot.id,
      code: lot.code,
      title: lot.title,
      status: 'live',
      current_bid: '550.00',
      minimum_bid: '575.00',
      ends_at: '2099-10-27T18:02:00.000Z',
      bids_count: 3,
      state_version: 11,
      server_time: '2026-10-27T12:01:00.000Z',
      my_position: null,
    })
    expect(merged.description).toBe(lot.description)
    expect(merged.current_bid).toBe('550.00')
    expect(merged.minimum_bid).toBe('575.00')
    expect(merged.my_position).toEqual(lot.my_position)
    expect(merged.state_version).toBe(11)
  })
})
