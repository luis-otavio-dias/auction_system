import type { JsonValue } from '../api/json'

export type Role = 'BIDDER' | 'SELLER'

export type LotStatus = 'live' | 'scheduled' | 'ended' | 'cancelled'

export type LotTab = 'live' | 'scheduled' | 'ended'

export type LotSort = 'ending' | 'price-high' | 'price-low' | 'recent'

export type MyPositionStatus = 'leading' | 'outbid' | 'no_bid'

export type ConnectionState = 'connecting' | 'open' | 'offline'

export interface User {
  id: string
  email: string
  role: Role
  public_alias: string
  full_name: string
  is_active: boolean
}

export type MyPosition = {
  is_leading: boolean
  status: MyPositionStatus
  last_amount: string | null
  rank: number | null
}

export type LotSummary = {
  id: string
  code: string
  status: LotStatus
  title: string
  image_url: string
  category: string
  starting_bid: string
  current_bid: string | null
  min_increment: string
  minimum_bid: string
  starts_at: string
  ends_at: string
  bids_count: number
  state_version: number
  seller_alias: string
}

export type LotDetail = LotSummary & {
  description: string
  source: string
  external_id: string
  source_url: string
  attributes: Record<string, JsonValue>
  original_ends_at: string
  extension_count: number
  my_position: MyPosition | null
  server_time: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface BidHistoryEntry {
  sequence: number
  amount: string
  bidder_alias: string
  placed_at: string
  is_mine: boolean
  prev_hash: string | null
  content_hash: string | null
  hash: string | null
}

export interface BidSubmission {
  accepted: boolean
  state_version: number | null
  lot: LotDetail | null
  bid: BidHistoryEntry | null
  detail: string | null
}

export type BidErrorCode =
  | 'LOT_NOT_STARTED'
  | 'LOT_ENDED'
  | 'LOT_CANCELLED'
  | 'LOT_SETTLED'
  | 'BID_AMOUNT_MISMATCH'
  | 'BID_BELOW_MINIMUM'
  | 'ALREADY_LEADING'
  | 'INSUFFICIENT_FUNDS'
  | 'SELLER_CANNOT_BID'
  | 'FORBIDDEN_ROLE'
  | 'IDEMPOTENCY_KEY_REUSED'

export interface Wallet {
  id: string | null
  balance: string
  committed: string
  available: string
  updated_at: string | null
}

export type WalletTransactionType =
  | 'DEPOSIT'
  | 'BID_HOLD'
  | 'BID_RELEASE'
  | 'SETTLEMENT_DEBIT'
  | 'SETTLEMENT_CREDIT'
  | 'CANCELLATION_RELEASE'
  | 'ADJUSTMENT_CREDIT'
  | 'ADJUSTMENT_DEBIT'
  | 'UNKNOWN'

export interface WalletTransaction {
  id: string
  type: WalletTransactionType
  amount: string
  balance_after: string
  committed_after: string
  reference_kind: string
  reference_id: string | null
  description: string
  created_at: string
}

export interface CatalogItem {
  id: string
  source: string
  external_id: string
  title: string
  description: string
  image_url: string
  thumbnail_url: string
  source_url: string
  category: string
  attributes: Record<string, JsonValue>
  fetched_at: string
}

export interface CatalogSearchResult {
  count: number
  from_cache: boolean
  degraded: boolean
  results: CatalogItem[]
}

export interface SellerLot {
  id: string
  code: string
  title: string
  status: LotStatus
  image_url: string
  category: string
  starting_bid: string
  current_bid: string | null
  min_increment: string
  minimum_bid: string
  starts_at: string
  ends_at: string
  bids_count: number
  state_version: number
  seller_alias: string
}

export interface SellerLotResult {
  lot_id: string
  code: string
  title: string
  final_price: string
  winner_alias: string
  settled_at: string | null
}

export interface SellerUnsoldLot {
  lot_id: string
  code: string
  title: string
  ends_at: string | null
}

export interface SellerBlockedLot {
  lot_id: string | null
  code: string
  title: string
  settlement_error: string
}

export interface SellerSummary {
  total_received: string
  settled_count: number
  unsold_count: number
  results: SellerLotResult[]
  unsold_lots: SellerUnsoldLot[]
  blocked_lots: SellerBlockedLot[]
}

export interface MyBid {
  lot_id: string | null
  lot_code: string
  lot_title: string
  sequence: number
  amount: string
  placed_at: string
  is_mine: boolean
}

export interface WinRecord {
  lot_id: string | null
  lot_code: string
  title: string
  final_price: string | null
  settled_at: string | null
  issued_at: string | null
  receipt_token: string
  share_url: string
}

export type AuditAnchorStatus = 'ok' | 'behind' | 'rollback_detected' | 'unavailable'

export interface AuditFailure {
  code: string
  sequence: number | null
  detail: string
}

export interface AuditBid {
  sequence: number
  amount: string
  bidder_alias: string
  placed_at: string
  prev_hash: string
  content_hash: string
  hash: string
}

export interface AuditReport {
  valid: boolean
  head_hash: string
  bid_count: number
  first_invalid_sequence: number | null
  anchor_status: AuditAnchorStatus
  failures: AuditFailure[]
  bids: AuditBid[]
  guarantees: string[]
  limitations: string[]
}

export interface Receipt {
  token: string
  code: string
  lot_code: string
  winner_alias: string
  seller_alias: string
  item_source: string
  item_external_id: string
  item_title: string
  item_image_url: string
  final_price: string
  issued_at: string
  audit_head: string
  bid_count: number
  share_url: string
}

export interface ReceiptVerification {
  receipt_valid: boolean
  history_valid: boolean
  head_matches: boolean
  bid_count: number
  anchor_status: AuditAnchorStatus
}

export interface WsTicket {
  ticket: string
}

export interface LotSnapshot {
  lot_id: string
  code: string
  title: string
  status: LotStatus
  current_bid: string | null
  minimum_bid: string
  ends_at: string
  bids_count: number
  state_version: number
  server_time: string
  my_position: MyPosition | null
}

export type LotEvent =
  | { type: 'lot.snapshot'; snapshot: LotSnapshot }
  | {
      type: 'bid.accepted'
      state_version: number
      current_bid: string | null
      minimum_bid: string | null
      bids_count: number | null
      ends_at: string | null
      bidder_alias: string | null
      sequence: number | null
    }
  | {
      type: 'lot.extended'
      state_version: number
      ends_at: string | null
      server_time: string | null
    }
  | {
      type: 'lot.closed'
      state_version: number
      final_price: string | null
      winner_alias: string | null
      receipt_token: string | null
    }
  | { type: 'lot.cancelled'; state_version: number; reason: string | null }

export interface AppNotification {
  id: string
  kind: 'outbid' | 'won' | 'sold'
  title: string
  message: string
  lot_id: string | null
  lot_href: string | null
  receipt_href: string | null
  href: string | null
  created_at: string
}
