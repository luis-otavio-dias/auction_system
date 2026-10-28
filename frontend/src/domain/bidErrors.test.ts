import { describe, expect, it } from 'vitest'
import { bidErrorMessage, GENERIC_BID_ERROR, isBidErrorCode } from './bidErrors'
import type { BidErrorCode } from '../types/api'

const CODES: readonly BidErrorCode[] = [
  'LOT_NOT_STARTED',
  'LOT_ENDED',
  'LOT_CANCELLED',
  'LOT_SETTLED',
  'BID_AMOUNT_MISMATCH',
  'BID_BELOW_MINIMUM',
  'ALREADY_LEADING',
  'INSUFFICIENT_FUNDS',
  'SELLER_CANNOT_BID',
  'FORBIDDEN_ROLE',
  'IDEMPOTENCY_KEY_REUSED',
]

describe('mensagens de erro de lance', () => {
  it('cobre todos os códigos do contrato com mensagens próprias', () => {
    const messages = CODES.map(code => bidErrorMessage(code))
    expect(new Set(messages).size).toBe(CODES.length)
    messages.forEach(message => {
      expect(message.length).toBeGreaterThan(10)
      expect(message).not.toBe(GENERIC_BID_ERROR)
    })
  })

  it('reconhece apenas códigos do contrato e usa o detalhe como fallback', () => {
    expect(isBidErrorCode('INSUFFICIENT_FUNDS')).toBe(true)
    expect(isBidErrorCode('OUTRO')).toBe(false)
    expect(bidErrorMessage('OUTRO', 'detalhe do backend')).toBe('detalhe do backend')
    expect(bidErrorMessage('OUTRO')).toBe(GENERIC_BID_ERROR)
  })
})
