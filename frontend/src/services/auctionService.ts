import type { Lot } from '../types/auction'
import lots from './lots.json'

const initialLots: Lot[] = lots

// Empty until catalog data is supplied by the backend.
export function getLots(): Lot[] {
  return initialLots.map(lot => ({ ...lot }))
}

export function getCategories(): string[] {
  return [...new Set(getLots().map(lot => lot.category))]
}
