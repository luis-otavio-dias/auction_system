import { requestJson, withQuery } from './client'
import { decodePaginated, decodeWallet, decodeWalletTransaction } from './decoders'
import type { Paginated, Wallet, WalletTransaction } from '../types/api'

export async function fetchWallet(): Promise<Wallet> {
  const payload = await requestJson('/api/wallet')
  if (payload === null) {
    throw new Error('Carteira sem resposta.')
  }
  return decodeWallet(payload)
}

export async function deposit(amount: string, idempotencyKey: string): Promise<void> {
  await requestJson('/api/wallet/deposits', {
    method: 'POST',
    body: { amount, idempotency_key: idempotencyKey },
  })
}

export async function fetchTransactions(page: number): Promise<Paginated<WalletTransaction>> {
  const payload = await requestJson(withQuery('/api/wallet/transactions', { page }))
  if (payload === null) {
    throw new Error('Extrato sem resposta.')
  }
  return decodePaginated(payload, 'extrato', decodeWalletTransaction)
}
