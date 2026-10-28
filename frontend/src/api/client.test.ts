import { describe, expect, it, vi } from 'vitest'
import { requestJson, ApiError } from './client'
import { installFetch, jsonReply } from '../test/apiMock'

describe('cliente HTTP', () => {
  it('renova a sessão uma vez em 401 e repete a requisição original', async () => {
    let meCalls = 0
    const calls = installFetch(url => {
      if (url.endsWith('/api/auth/me/')) {
        meCalls += 1
        return meCalls === 1 ? jsonReply({ detail: 'expirado' }, 401) : jsonReply({ id: 'u-1', email: 'a@b.com' })
      }
      if (url.endsWith('/api/auth/refresh/')) {
        return jsonReply({ detail: 'renovado' })
      }
      return jsonReply({ detail: 'inesperado' }, 500)
    })

    const payload = await requestJson('/api/auth/me/')

    expect(payload).toEqual({ id: 'u-1', email: 'a@b.com' })
    expect(calls.map(call => call.url)).toEqual([
      'http://localhost:8001/api/auth/me/',
      'http://localhost:8001/api/auth/refresh/',
      'http://localhost:8001/api/auth/me/',
    ])
    expect(calls.every(call => call.credentials === 'include')).toBe(true)
  })

  it('emite expiração de sessão quando o refresh também falha', async () => {
    const onExpired = vi.fn()
    window.addEventListener('auth:expired', onExpired)
    installFetch(url => {
      if (url.endsWith('/api/auth/refresh/')) {
        return jsonReply({ detail: 'refresh inválido' }, 401)
      }
      return jsonReply({ detail: 'expirado' }, 401)
    })

    await expect(requestJson('/api/auth/me/')).rejects.toBeInstanceOf(ApiError)
    expect(onExpired).toHaveBeenCalledTimes(1)
    window.removeEventListener('auth:expired', onExpired)
  })

  it('preserva o código e a mensagem de erro da API', async () => {
    installFetch(() => jsonReply({ code: 'BID_AMOUNT_MISMATCH', detail: 'valor diferente' }, 422))

    await expect(requestJson('/api/lots/lot-1/bids', { method: 'POST', body: { amount: '1.00' } }))
      .rejects.toMatchObject({ code: 'BID_AMOUNT_MISMATCH', status: 422, detail: 'valor diferente' })
  })
})
