import { requestJson, withQuery } from './client'
import { decodeAuditReport, decodeCatalogSearch, decodeReceipt, decodeReceiptVerification } from './decoders'
import type { AuditReport, CatalogSearchResult, Receipt, ReceiptVerification } from '../types/api'

export async function searchCatalog(query: string, signal?: AbortSignal): Promise<CatalogSearchResult> {
  const payload = await requestJson(withQuery('/api/catalog/search', { q: query }), { signal })
  if (payload === null) {
    throw new Error('Catálogo sem resposta.')
  }
  return decodeCatalogSearch(payload)
}

export async function fetchAudit(lotId: string, signal?: AbortSignal): Promise<AuditReport> {
  const payload = await requestJson(`/api/lots/${lotId}/audit`, { signal })
  if (payload === null) {
    throw new Error('Auditoria sem resposta.')
  }
  return decodeAuditReport(payload)
}

export async function fetchReceipt(token: string, signal?: AbortSignal): Promise<Receipt> {
  const payload = await requestJson(`/api/receipts/${token}`, { signal })
  if (payload === null) {
    throw new Error('Comprovante sem resposta.')
  }
  return decodeReceipt(payload, token)
}

export async function verifyReceipt(token: string, signal?: AbortSignal): Promise<ReceiptVerification> {
  const payload = await requestJson(`/api/receipts/${token}/verify`, { signal })
  if (payload === null) {
    throw new Error('Verificação sem resposta.')
  }
  return decodeReceiptVerification(payload)
}
