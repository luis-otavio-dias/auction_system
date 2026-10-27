import type { CatalogFilters, Lot } from '../types/auction'

export function filterLots(lots: Lot[], filters: CatalogFilters): Lot[] {
  const { tab, category, query, reserveOnly, sort } = filters
  return (tab === 'live' ? lots : [])
    .filter(lot =>
      (!category || lot.category === category) &&
      (!reserveOnly || lot.status === 'Reserva Atingida') &&
      `${lot.title} ${lot.provenance} ${lot.id}`
        .toLocaleLowerCase('pt-BR')
        .includes(query.toLocaleLowerCase('pt-BR')),
    )
    .sort((a, b) => sort === 'price-high'
      ? b.bid - a.bid
      : sort === 'price-low' ? a.bid - b.bid : a.seconds - b.seconds)
}
