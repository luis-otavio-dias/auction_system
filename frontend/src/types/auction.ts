export interface Lot {
  id: string
  title: string
  description: string
  provenance: string
  status: string
  image: string
  alt: string
  bid: number
  increment: number
  seconds: number
  estimate: string
  category: string
}

export type AuctionTab = 'live' | 'scheduled' | 'results'
export type LotSort = 'ending' | 'price-high' | 'price-low'

export interface CatalogFilters {
  tab: AuctionTab
  category: string
  query: string
  reserveOnly: boolean
  sort: LotSort
}
