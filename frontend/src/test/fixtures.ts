import type { LotDetail, LotSummary, User } from '../types/api'

export const bidderUser: User = {
  id: 'u-bidder',
  email: 'cliente1@demo.com',
  role: 'BIDDER',
  public_alias: 'Cliente Um',
  full_name: 'Cliente Um',
  is_active: true,
}

export const sellerUser: User = {
  id: 'u-seller',
  email: 'leiloeiro@demo.com',
  role: 'SELLER',
  public_alias: 'Leiloeiro Demo',
  full_name: 'Leiloeiro Demo',
  is_active: true,
}

export function lotSummary(overrides: Partial<LotSummary> = {}): LotSummary {
  return {
    id: 'lot-1',
    code: 'L-000000001',
    status: 'live',
    title: 'Noite sobre o Sena',
    image_url: 'https://example.test/lot.jpg',
    category: 'Pintura',
    starting_bid: '500.00',
    current_bid: '500.00',
    min_increment: '25.00',
    minimum_bid: '525.00',
    starts_at: '2026-10-27T10:00:00.000Z',
    ends_at: '2099-10-27T18:00:00.000Z',
    bids_count: 1,
    state_version: 10,
    seller_alias: 'Leiloeiro Demo',
    ...overrides,
  }
}

export function lotDetail(overrides: Partial<LotDetail> = {}): LotDetail {
  return {
    ...lotSummary(),
    description: 'Óleo sobre tela, assinado.',
    source: 'artic',
    external_id: '12345',
    source_url: 'https://example.test/item',
    attributes: { artista: 'Exemplo', técnica: 'Óleo' },
    original_ends_at: '2099-10-27T18:00:00.000Z',
    extension_count: 0,
    my_position: {
      is_leading: false,
      status: 'no_bid',
      last_amount: null,
      rank: null,
    },
    server_time: '2026-10-27T12:00:00.000Z',
    ...overrides,
  }
}
