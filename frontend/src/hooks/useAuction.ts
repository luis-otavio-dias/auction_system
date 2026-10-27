import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Lot } from '../types/auction'
import { getLots } from '../services/auctionService'
import { money } from '../utils/format'

export function useAuction(elapsed: number, onBid: (message: string) => void) {
  const [lots, setLots] = useState(getLots)
  const [activeLot, setActiveLot] = useState<Lot | null>(null)
  const [bidValue, setBidValue] = useState('')
  const [bidError, setBidError] = useState('')

  const openBid = (lot: Lot) => {
    setActiveLot(lot)
    setBidValue(String(lot.bid + lot.increment))
    setBidError('')
  }
  const closeBid = () => setActiveLot(null)
  const changeBidValue = (value: string) => {
    setBidValue(value)
    setBidError('')
  }
  const submitBid = (event: FormEvent) => {
    event.preventDefault()
    if (!activeLot) return
    const amount = Number(bidValue)
    if (activeLot.seconds <= elapsed) {
      setBidError('O período de lances deste lote foi encerrado.')
      return
    }
    if (!Number.isSafeInteger(amount) || amount < activeLot.bid + activeLot.increment) {
      setBidError(`O lance mínimo é ${money(activeLot.bid + activeLot.increment)}.`)
      return
    }
    setLots(current => current.map(lot => lot.id === activeLot.id ? { ...lot, bid: amount } : lot))
    onBid(`Lance demonstrativo de ${money(amount)} registrado para o lote ${activeLot.id.padStart(3, '0')}.`)
    closeBid()
  }

  return { lots, activeLot, bidValue, bidError, openBid, closeBid, changeBidValue, submitBid }
}
