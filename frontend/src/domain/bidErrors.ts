import type { BidErrorCode } from '../types/api'

const BID_ERROR_CODES: readonly BidErrorCode[] = [
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

const BID_ERROR_MESSAGES: Record<BidErrorCode, string> = {
  LOT_NOT_STARTED: 'O lote ainda não começou. Aguarde a abertura do pregão.',
  LOT_ENDED: 'O lote já foi encerrado e não aceita novos lances.',
  LOT_CANCELLED: 'O lote foi cancelado pelo leiloeiro.',
  LOT_SETTLED: 'O lote já foi liquidado.',
  BID_AMOUNT_MISMATCH: 'O valor precisa ser exatamente o mínimo exibido para este lote.',
  BID_BELOW_MINIMUM: 'O valor informado está abaixo do mínimo permitido.',
  ALREADY_LEADING: 'Você já é o líder deste lote e não pode cobrir o próprio lance.',
  INSUFFICIENT_FUNDS: 'Saldo disponível insuficiente. Faça um depósito na carteira.',
  SELLER_CANNOT_BID: 'O leiloeiro não pode dar lance no próprio lote.',
  FORBIDDEN_ROLE: 'Seu perfil não tem permissão para dar lances.',
  IDEMPOTENCY_KEY_REUSED: 'Este envio já foi usado com outro valor. Revise o valor e tente novamente.',
}

export function isBidErrorCode(value: string): value is BidErrorCode {
  return BID_ERROR_CODES.some(code => code === value)
}

export function bidErrorMessage(code: string, detail?: string | null): string {
  if (isBidErrorCode(code)) {
    return BID_ERROR_MESSAGES[code]
  }
  if (detail && detail.trim() !== '') {
    return detail
  }
  return 'Não foi possível registrar o lance. Tente novamente.'
}

export const GENERIC_BID_ERROR = 'Não foi possível registrar o lance. Tente novamente.'
