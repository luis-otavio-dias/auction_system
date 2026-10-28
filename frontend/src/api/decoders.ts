import {
  DecodeError,
  booleanField,
  decimalField,
  expectArray,
  expectObject,
  firstNumber,
  firstObject,
  firstString,
  isJsonObject,
  numberField,
  objectField,
  optionalDecimal,
  optionalString,
  stringList,
  textField,
} from './json'
import type { JsonObject, JsonValue } from './json'
import type {
  AppNotification,
  AuditAnchorStatus,
  AuditBid,
  AuditFailure,
  AuditReport,
  BidHistoryEntry,
  BidSubmission,
  CatalogItem,
  CatalogSearchResult,
  LotDetail,
  LotEvent,
  LotSnapshot,
  LotStatus,
  LotSummary,
  MyBid,
  MyPosition,
  MyPositionStatus,
  Paginated,
  Receipt,
  ReceiptVerification,
  Role,
  SellerBlockedLot,
  SellerLot,
  SellerLotResult,
  SellerSummary,
  SellerUnsoldLot,
  User,
  Wallet,
  WalletTransaction,
  WalletTransactionType,
  WinRecord,
  WsTicket,
} from '../types/api'

const LOT_STATUSES: readonly LotStatus[] = ['live', 'scheduled', 'ended', 'cancelled']
const ROLES: readonly Role[] = ['BIDDER', 'SELLER']
const POSITION_STATUSES: readonly MyPositionStatus[] = ['leading', 'outbid', 'no_bid']
const ANCHOR_STATUSES: readonly AuditAnchorStatus[] = ['ok', 'behind', 'rollback_detected', 'unavailable']
const TRANSACTION_TYPES: readonly WalletTransactionType[] = [
  'DEPOSIT',
  'BID_HOLD',
  'BID_RELEASE',
  'SETTLEMENT_DEBIT',
  'SETTLEMENT_CREDIT',
  'CANCELLATION_RELEASE',
  'ADJUSTMENT_CREDIT',
  'ADJUSTMENT_DEBIT',
  'UNKNOWN',
]

function tupleIncludes<T extends string>(values: readonly T[], candidate: string): candidate is T {
  return values.some(value => value === candidate)
}

function decodeRole(value: JsonValue | undefined): Role {
  const role = typeof value === 'string' ? value : ''
  return tupleIncludes(ROLES, role) ? role : 'BIDDER'
}

function decodeLotStatus(value: JsonValue | undefined): LotStatus {
  const status = typeof value === 'string' ? value : ''
  return tupleIncludes(LOT_STATUSES, status) ? status : 'ended'
}

function decodePositionStatus(value: JsonValue | undefined): MyPositionStatus {
  const status = typeof value === 'string' ? value : ''
  return tupleIncludes(POSITION_STATUSES, status) ? status : 'no_bid'
}

function decodeAnchorStatus(value: JsonValue | undefined): AuditAnchorStatus {
  const status = typeof value === 'string' ? value : ''
  return tupleIncludes(ANCHOR_STATUSES, status) ? status : 'unavailable'
}

function decodeTransactionType(value: JsonValue | undefined): WalletTransactionType {
  const type = typeof value === 'string' ? value : ''
  return tupleIncludes(TRANSACTION_TYPES, type) ? type : 'UNKNOWN'
}

export function decodeUser(value: JsonValue): User {
  const source = expectObject(value, 'usuário')
  return {
    id: textField(source, 'id'),
    email: textField(source, 'email'),
    role: decodeRole(source.role),
    public_alias: textField(source, 'public_alias'),
    full_name: textField(source, 'full_name'),
    is_active: booleanField(source, 'is_active', true),
  }
}

export function decodeMyPosition(value: JsonValue | undefined): MyPosition | null {
  if (!isJsonObject(value)) {
    return null
  }
  const status = decodePositionStatus(value.status)
  return {
    is_leading: booleanField(value, 'is_leading', status === 'leading'),
    status,
    last_amount: optionalDecimal(value, 'last_amount'),
    rank: firstNumber(value, ['rank', 'position']),
  }
}

export function decodeLotSummary(value: JsonValue): LotSummary {
  const source = expectObject(value, 'lote')
  const seller = firstObject(source, ['seller'])
  const currentBid = optionalDecimal(source, 'current_bid')
  const minIncrement = decimalField(source, 'min_increment', '0.00')
  const minimumBid =
    optionalDecimal(source, 'minimum_bid')
    ?? (currentBid !== null ? (Number(currentBid) + Number(minIncrement)).toFixed(2) : decimalField(source, 'starting_bid'))
  return {
    id: firstString(source, ['id', 'lot_id']) ?? '',
    code: firstString(source, ['code', 'lot_code']) ?? '',
    status: decodeLotStatus(source.status),
    title: textField(source, 'title'),
    image_url: firstString(source, ['image_url', 'image']) ?? '',
    category: textField(source, 'category'),
    starting_bid: decimalField(source, 'starting_bid'),
    current_bid: currentBid,
    min_increment: minIncrement,
    minimum_bid: minimumBid,
    starts_at: textField(source, 'starts_at'),
    ends_at: textField(source, 'ends_at'),
    bids_count: numberField(source, 'bids_count'),
    state_version: numberField(source, 'state_version', 1),
    seller_alias:
      firstString(source, ['seller_alias'])
      ?? (seller ? textField(seller, 'public_alias') : ''),
  }
}

export function decodeLotDetail(value: JsonValue): LotDetail {
  const source = expectObject(value, 'detalhe do lote')
  const summary = decodeLotSummary(source)
  return {
    ...summary,
    description: textField(source, 'description'),
    source: textField(source, 'source'),
    external_id: textField(source, 'external_id'),
    source_url: textField(source, 'source_url'),
    attributes: objectField(source, 'attributes'),
    original_ends_at: firstString(source, ['original_ends_at']) ?? summary.ends_at,
    extension_count: numberField(source, 'extension_count'),
    my_position: decodeMyPosition(source.my_position),
    server_time: firstString(source, ['server_time']) ?? new Date().toISOString(),
  }
}

export function decodePaginated<T>(
  value: JsonValue,
  context: string,
  decodeItem: (item: JsonValue) => T,
): Paginated<T> {
  if (Array.isArray(value)) {
    return {
      count: value.length,
      next: null,
      previous: null,
      results: value.map(decodeItem),
    }
  }
  const source = expectObject(value, context)
  const results = expectArray(source.results, context)
  return {
    count: numberField(source, 'count', results.length),
    next: optionalString(source.next),
    previous: optionalString(source.previous),
    results: results.map(decodeItem),
  }
}

export function decodeBid(value: JsonValue): BidHistoryEntry {
  const source = expectObject(value, 'lance')
  return {
    sequence: numberField(source, 'sequence'),
    amount: decimalField(source, 'amount'),
    bidder_alias: textField(source, 'bidder_alias'),
    placed_at: textField(source, 'placed_at'),
    is_mine: booleanField(source, 'is_mine'),
    prev_hash: optionalString(source.prev_hash),
    content_hash: optionalString(source.content_hash),
    hash: optionalString(source.hash),
  }
}

export function decodeBidSubmission(value: JsonValue): BidSubmission {
  const source = expectObject(value, 'resposta do lance')
  const lotSource = firstObject(source, ['lot', 'detail'])
  const bidSource = firstObject(source, ['bid', 'accepted_bid'])
  return {
    accepted: true,
    state_version: firstNumber(source, ['state_version']),
    lot: lotSource
      ? decodeLotDetail(lotSource)
      : typeof source.starts_at === 'string' ? decodeLotDetail(source) : null,
    bid: bidSource
      ? decodeBid(bidSource)
      : source.sequence !== undefined && source.amount !== undefined ? decodeBid(source) : null,
    detail: firstString(source, ['detail']),
  }
}

export function decodeWallet(value: JsonValue): Wallet {
  const root = expectObject(value, 'carteira')
  const source = firstObject(root, ['wallet']) ?? root
  const balance = decimalField(source, 'balance')
  const committed = decimalField(source, 'committed')
  return {
    id: firstString(source, ['id']),
    balance,
    committed,
    available:
      optionalDecimal(source, 'available')
      ?? (Number(balance) - Number(committed)).toFixed(2),
    updated_at: firstString(source, ['updated_at']),
  }
}

export function decodeWalletTransaction(value: JsonValue): WalletTransaction {
  const source = expectObject(value, 'lançamento')
  return {
    id: textField(source, 'id'),
    type: decodeTransactionType(source.type),
    amount: decimalField(source, 'amount'),
    balance_after: decimalField(source, 'balance_after'),
    committed_after: decimalField(source, 'committed_after'),
    reference_kind: textField(source, 'reference_kind', 'NONE'),
    reference_id: optionalString(source.reference_id),
    description: textField(source, 'description'),
    created_at: textField(source, 'created_at'),
  }
}

export function decodeCatalogItem(value: JsonValue): CatalogItem {
  const source = expectObject(value, 'item do catálogo')
  return {
    id: firstString(source, ['id', 'catalog_item_id']) ?? '',
    source: textField(source, 'source'),
    external_id: textField(source, 'external_id'),
    title: textField(source, 'title'),
    description: textField(source, 'description'),
    image_url: textField(source, 'image_url'),
    thumbnail_url: textField(source, 'thumbnail_url'),
    source_url: textField(source, 'source_url'),
    category: textField(source, 'category'),
    attributes: objectField(source, 'attributes'),
    fetched_at: textField(source, 'fetched_at'),
  }
}

export function decodeCatalogSearch(value: JsonValue): CatalogSearchResult {
  const source = expectObject(value, 'busca no catálogo')
  const results = expectArray(source.results, 'busca no catálogo')
  return {
    count: numberField(source, 'count', results.length),
    from_cache: booleanField(source, 'from_cache'),
    degraded: booleanField(source, 'degraded'),
    results: results.map(decodeCatalogItem),
  }
}

export function decodeSellerLot(value: JsonValue): SellerLot {
  const summary = decodeLotSummary(value)
  return {
    id: summary.id,
    code: summary.code,
    title: summary.title,
    status: summary.status,
    image_url: summary.image_url,
    category: summary.category,
    starting_bid: summary.starting_bid,
    current_bid: summary.current_bid,
    min_increment: summary.min_increment,
    minimum_bid: summary.minimum_bid,
    starts_at: summary.starts_at,
    ends_at: summary.ends_at,
    bids_count: summary.bids_count,
    state_version: summary.state_version,
    seller_alias: summary.seller_alias,
  }
}

function decodeSellerLotResult(value: JsonValue): SellerLotResult {
  const source = expectObject(value, 'resultado do lote')
  return {
    lot_id: firstString(source, ['lot_id', 'id']) ?? '',
    code: firstString(source, ['code', 'lot_code']) ?? '',
    title: textField(source, 'title'),
    final_price: decimalField(source, 'final_price'),
    winner_alias: firstString(source, ['winner_alias']) ?? '',
    settled_at: firstString(source, ['settled_at', 'issued_at']),
  }
}

function decodeSellerUnsoldLot(value: JsonValue): SellerUnsoldLot {
  const source = expectObject(value, 'lote sem arremate')
  return {
    lot_id: firstString(source, ['lot_id', 'id']) ?? '',
    code: firstString(source, ['code', 'lot_code']) ?? '',
    title: textField(source, 'title'),
    ends_at: firstString(source, ['ends_at', 'closed_at', 'settled_at']),
  }
}

function decodeSellerBlockedLot(value: JsonValue): SellerBlockedLot {
  const source = expectObject(value, 'lote bloqueado')
  return {
    lot_id: firstString(source, ['lot_id', 'id']),
    code: textField(source, 'code'),
    title: textField(source, 'title'),
    settlement_error: textField(source, 'settlement_error'),
  }
}

function listField(source: JsonObject, keys: readonly string[]): JsonValue[] {
  for (const key of keys) {
    const value = source[key]
    if (Array.isArray(value)) {
      return value
    }
  }
  return []
}

export function decodeSellerSummary(value: JsonValue): SellerSummary {
  const source = expectObject(value, 'resumo do leiloeiro')
  return {
    total_received: decimalField(source, 'total_received'),
    settled_count: numberField(source, 'settled_count'),
    unsold_count: numberField(source, 'unsold_count'),
    results: listField(source, ['results_by_lot', 'results', 'settled_lots', 'lot_results']).map(decodeSellerLotResult),
    unsold_lots: listField(source, ['unsold_lots', 'lots_without_winner', 'unsold']).map(decodeSellerUnsoldLot),
    blocked_lots: listField(source, ['blocked_lots', 'blocked']).map(decodeSellerBlockedLot),
  }
}

export function decodeMyBid(value: JsonValue): MyBid {
  const source = expectObject(value, 'lance do licitante')
  return {
    lot_id: firstString(source, ['lot_id', 'id']),
    lot_code: firstString(source, ['lot_code', 'code']) ?? '',
    lot_title: firstString(source, ['lot_title', 'title']) ?? '',
    sequence: numberField(source, 'sequence'),
    amount: decimalField(source, 'amount'),
    placed_at: textField(source, 'placed_at'),
    is_mine: booleanField(source, 'is_mine', true),
  }
}

export function decodeWin(value: JsonValue): WinRecord {
  const source = expectObject(value, 'arremate')
  const token = firstString(source, ['receipt_token', 'token'])
  if (token === null || token === '') {
    throw new DecodeError('Comprovante ausente no arremate.')
  }
  return {
    lot_id: firstString(source, ['lot_id', 'id']),
    lot_code: firstString(source, ['lot_code', 'code']) ?? '',
    title: textField(source, 'title'),
    final_price: optionalDecimal(source, 'final_price'),
    settled_at: firstString(source, ['settled_at']),
    issued_at: firstString(source, ['issued_at', 'settled_at']),
    receipt_token: token,
    share_url: firstString(source, ['share_url', 'receipt_url']) ?? '',
  }
}

function decodeAuditFailure(value: JsonValue, index: number): AuditFailure {
  if (typeof value === 'string') {
    return { code: value, sequence: null, detail: '' }
  }
  const source = expectObject(value, 'falha de auditoria')
  return {
    code: firstString(source, ['code', 'failure']) ?? `FAILURE_${index + 1}`,
    sequence: firstNumber(source, ['sequence', 'first_invalid_sequence']),
    detail: textField(source, 'detail'),
  }
}

function decodeAuditBid(value: JsonValue): AuditBid {
  const source = expectObject(value, 'lance auditado')
  return {
    sequence: numberField(source, 'sequence'),
    amount: decimalField(source, 'amount'),
    bidder_alias: textField(source, 'bidder_alias'),
    placed_at: textField(source, 'placed_at'),
    prev_hash: textField(source, 'prev_hash'),
    content_hash: textField(source, 'content_hash'),
    hash: textField(source, 'hash'),
  }
}

export function decodeAuditReport(value: JsonValue): AuditReport {
  const source = expectObject(value, 'auditoria')
  const rawFailures = source.failures
  const failures = Array.isArray(rawFailures) ? rawFailures.map(decodeAuditFailure) : []
  const rawBids = source.bids ?? source.history ?? source.bid_history
  const bids = Array.isArray(rawBids) ? rawBids.map(decodeAuditBid) : []
  return {
    valid: booleanField(source, 'valid'),
    head_hash: textField(source, 'head_hash'),
    bid_count: numberField(source, 'bid_count', bids.length),
    first_invalid_sequence: firstNumber(source, ['first_invalid_sequence']),
    anchor_status: decodeAnchorStatus(source.anchor_status),
    failures,
    bids,
    guarantees: stringList(source, 'guarantees'),
    limitations: stringList(source, 'limitations'),
  }
}

export function decodeReceipt(value: JsonValue, fallbackToken: string): Receipt {
  const root = expectObject(value, 'comprovante')
  const source = firstObject(root, ['receipt']) ?? root
  const receiptUrl = firstString(source, ['share_url', 'receipt_url']) ?? ''
  return {
    token: firstString(source, ['token']) ?? fallbackToken,
    code: textField(source, 'code'),
    lot_code: textField(source, 'lot_code'),
    winner_alias: textField(source, 'winner_alias'),
    seller_alias: textField(source, 'seller_alias'),
    item_source: textField(source, 'item_source'),
    item_external_id: textField(source, 'item_external_id'),
    item_title: textField(source, 'item_title'),
    item_image_url: textField(source, 'item_image_url'),
    final_price: decimalField(source, 'final_price'),
    issued_at: textField(source, 'issued_at'),
    audit_head: textField(source, 'audit_head'),
    bid_count: numberField(source, 'bid_count'),
    share_url: receiptUrl,
  }
}

export function decodeReceiptVerification(value: JsonValue): ReceiptVerification {
  const source = expectObject(value, 'verificação do comprovante')
  return {
    receipt_valid: booleanField(source, 'receipt_valid'),
    history_valid: booleanField(source, 'history_valid'),
    head_matches: booleanField(source, 'head_matches'),
    bid_count: numberField(source, 'bid_count'),
    anchor_status: decodeAnchorStatus(source.anchor_status),
  }
}

export function decodeWsTicket(value: JsonValue): WsTicket {
  const source = expectObject(value, 'ticket de WebSocket')
  const ticket = firstString(source, ['ticket', 'token'])
  if (ticket === null || ticket === '') {
    throw new DecodeError('Ticket de WebSocket ausente.')
  }
  return { ticket }
}

function eventPayload(source: JsonObject): JsonObject {
  return firstObject(source, ['data', 'payload', 'event']) ?? source
}

export function decodeLotSnapshot(value: JsonValue): LotSnapshot {
  const source = expectObject(value, 'snapshot do lote')
  return {
    lot_id: firstString(source, ['lot_id', 'id']) ?? '',
    code: firstString(source, ['code', 'lot_code']) ?? '',
    title: textField(source, 'title'),
    status: decodeLotStatus(source.status),
    current_bid: optionalDecimal(source, 'current_bid'),
    minimum_bid: decimalField(source, 'minimum_bid'),
    ends_at: textField(source, 'ends_at'),
    bids_count: numberField(source, 'bids_count'),
    state_version: numberField(source, 'state_version', 1),
    server_time: textField(source, 'server_time'),
    my_position: decodeMyPosition(source.my_position),
  }
}

export function decodeLotEvent(value: JsonValue): LotEvent | null {
  const root = expectObject(value, 'evento do lote')
  const type = firstString(root, ['type', 'event', 'kind'])
  const payload = eventPayload(root)
  if (type === 'lot.snapshot') {
    return { type, snapshot: decodeLotSnapshot(payload) }
  }
  const version = firstNumber(payload, ['state_version']) ?? firstNumber(root, ['state_version'])
  if (version === null) {
    return null
  }
  if (type === 'bid.accepted') {
    return {
      type,
      state_version: version,
      current_bid: optionalDecimal(payload, 'current_bid') ?? optionalDecimal(payload, 'amount'),
      minimum_bid: optionalDecimal(payload, 'minimum_bid'),
      bids_count: firstNumber(payload, ['bids_count', 'bid_count', 'count']),
      ends_at: firstString(payload, ['ends_at']),
      bidder_alias: firstString(payload, ['bidder_alias']),
      sequence: firstNumber(payload, ['sequence']),
    }
  }
  if (type === 'lot.extended') {
    return {
      type,
      state_version: version,
      ends_at: firstString(payload, ['ends_at']),
      server_time: firstString(payload, ['server_time']),
    }
  }
  if (type === 'lot.closed') {
    const receipt = firstObject(payload, ['receipt'])
    return {
      type,
      state_version: version,
      final_price: optionalDecimal(payload, 'final_price'),
      winner_alias: firstString(payload, ['winner_alias']),
      receipt_token:
        firstString(payload, ['receipt_token', 'token'])
        ?? (receipt ? firstString(receipt, ['token']) : null),
    }
  }
  if (type === 'lot.cancelled') {
    return {
      type,
      state_version: version,
      reason: firstString(payload, ['cancel_reason', 'reason']),
    }
  }
  return null
}

export function decodeNotification(value: JsonValue): AppNotification | null {
  const root = expectObject(value, 'notificação')
  const type = firstString(root, ['type', 'event', 'kind'])
  const payload = eventPayload(root)
  const lotId = firstString(payload, ['lot_id'])
  const lotCode = firstString(payload, ['lot_code', 'code']) ?? ''
  const amount = optionalDecimal(payload, 'amount') ?? optionalDecimal(payload, 'final_price')
  const createdAt = firstString(payload, ['created_at', 'placed_at', 'server_time']) ?? new Date().toISOString()
  const receiptObject = firstObject(payload, ['receipt'])
  const receiptToken =
    firstString(payload, ['receipt_token', 'token'])
    ?? (receiptObject ? firstString(receiptObject, ['token']) : null)
  const receiptUrl =
    firstString(payload, ['receipt_url', 'share_url'])
    ?? (receiptObject ? firstString(receiptObject, ['share_url', 'url']) : null)
  const lotHref = lotId ? `/lotes/${lotId}` : null
  const receiptHref =
    receiptUrl
    ?? (receiptToken ? `/comprovantes/${receiptToken}` : null)
  if (type === 'user.outbid') {
    return {
      id: `${type}-${lotId ?? 'lot'}-${createdAt}`,
      kind: 'outbid',
      title: 'Você foi superado',
      message: amount
        ? `O lote ${lotCode || lotId || ''} recebeu um lance de ${amount}.`
        : `Seu lance no lote ${lotCode || lotId || ''} foi superado.`,
      lot_id: lotId,
      lot_href: lotHref,
      receipt_href: receiptHref,
      href: lotHref ?? receiptHref,
      created_at: createdAt,
    }
  }
  if (type === 'user.won') {
    return {
      id: `${type}-${lotId ?? 'lot'}-${createdAt}`,
      kind: 'won',
      title: 'Você arrematou',
      message: amount
        ? `Lote ${lotCode || lotId || ''} arrematado por ${amount}.`
        : `Você venceu o lote ${lotCode || lotId || ''}.`,
      lot_id: lotId,
      lot_href: lotHref,
      receipt_href: receiptHref,
      href: receiptHref ?? lotHref,
      created_at: createdAt,
    }
  }
  if (type === 'user.sold') {
    return {
      id: `${type}-${lotId ?? 'lot'}-${createdAt}`,
      kind: 'sold',
      title: 'Lote vendido',
      message: amount
        ? `Lote ${lotCode || lotId || ''} vendido por ${amount}.`
        : `Seu lote ${lotCode || lotId || ''} foi vendido.`,
      lot_id: lotId,
      lot_href: lotHref,
      receipt_href: receiptHref,
      href: lotHref ?? receiptHref,
      created_at: createdAt,
    }
  }
  return null
}
