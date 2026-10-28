import { requestJson, withQuery } from './client'
import {
  decodeBid,
  decodeBidSubmission,
  decodeLotDetail,
  decodeLotSummary,
  decodeMyBid,
  decodePaginated,
  decodeSellerLot,
  decodeSellerSummary,
  decodeWin,
} from './decoders'
import type { BidHistoryEntry, BidSubmission, LotDetail, LotSort, LotSummary, MyBid, Paginated, SellerLot, SellerSummary, WinRecord } from '../types/api'

export interface LotListParams {
  tab: string
  q: string
  category: string
  sort: LotSort
  page: number
}

export async function listLots(params: LotListParams, signal?: AbortSignal): Promise<Paginated<LotSummary>> {
  const payload = await requestJson(withQuery('/api/lots', {
    tab: params.tab,
    q: params.q,
    category: params.category,
    sort: params.sort,
    page: params.page,
  }), { signal })
  if (payload === null) {
    throw new Error('Vitrine sem resposta.')
  }
  return decodePaginated(payload, 'vitrine', decodeLotSummary)
}

export async function getLot(id: string, signal?: AbortSignal): Promise<LotDetail> {
  const payload = await requestJson(`/api/lots/${id}`, { signal })
  if (payload === null) {
    throw new Error('Lote sem resposta.')
  }
  return decodeLotDetail(payload)
}

export async function listBids(id: string, page: number, signal?: AbortSignal): Promise<Paginated<BidHistoryEntry>> {
  const payload = await requestJson(withQuery(`/api/lots/${id}/bids`, { page }), { signal })
  if (payload === null) {
    throw new Error('Histórico sem resposta.')
  }
  return decodePaginated(payload, 'histórico de lances', decodeBid)
}

export async function placeBid(
  lotId: string,
  amount: string,
  clientBidId: string,
): Promise<BidSubmission> {
  const payload = await requestJson(`/api/lots/${lotId}/bids`, {
    method: 'POST',
    body: {
      amount,
      client_bid_id: clientBidId,
    },
  })
  if (payload === null) {
    throw new Error('Resposta vazia ao registrar o lance.')
  }
  return decodeBidSubmission(payload)
}

export async function cancelLot(lotId: string, reason: string): Promise<LotDetail> {
  const payload = await requestJson(`/api/lots/${lotId}/cancel`, {
    method: 'POST',
    body: { reason },
  })
  if (payload === null) {
    throw new Error('Resposta vazia ao cancelar o lote.')
  }
  return decodeLotDetail(payload)
}

export async function createLot(input: {
  catalog_item_id: string
  starts_at: string
  ends_at: string
  starting_bid: string
  min_increment: string
}): Promise<LotDetail> {
  const payload = await requestJson('/api/lots', {
    method: 'POST',
    body: {
      catalog_item_id: input.catalog_item_id,
      starts_at: input.starts_at,
      ends_at: input.ends_at,
      starting_bid: input.starting_bid,
      min_increment: input.min_increment,
    },
  })
  if (payload === null) {
    throw new Error('Resposta vazia ao criar o lote.')
  }
  return decodeLotDetail(payload)
}

export async function fetchSellerLots(page = 1): Promise<Paginated<SellerLot>> {
  const payload = await requestJson(withQuery('/api/seller/lots', { page }))
  if (payload === null) {
    throw new Error('Painel sem resposta.')
  }
  return decodePaginated(payload, 'lotes do leiloeiro', decodeSellerLot)
}

export async function fetchSellerSummary(): Promise<SellerSummary> {
  const payload = await requestJson('/api/seller/summary')
  if (payload === null) {
    throw new Error('Resumo sem resposta.')
  }
  return decodeSellerSummary(payload)
}

export async function fetchMyBids(page = 1): Promise<Paginated<MyBid>> {
  const payload = await requestJson(withQuery('/api/me/bids', { page }))
  if (payload === null) {
    throw new Error('Lances sem resposta.')
  }
  return decodePaginated(payload, 'meus lances', decodeMyBid)
}

export async function fetchMyWins(): Promise<WinRecord[]> {
  const payload = await requestJson('/api/me/wins')
  if (!Array.isArray(payload)) {
    throw new Error('Arremates sem resposta.')
  }
  return payload.map(decodeWin)
}
