import { requestJson, requestWithSlashFallback } from './client'
import { decodeUser, decodeWsTicket } from './decoders'
import type { Role, User, WsTicket } from '../types/api'

export async function login(email: string, password: string): Promise<void> {
  await requestJson('/api/auth/token/', {
    method: 'POST',
    body: { email, password },
  })
}

export async function register(input: {
  email: string
  password: string
  role: Role
  public_alias: string
}): Promise<void> {
  await requestWithSlashFallback('/api/auth/register', {
    method: 'POST',
    body: {
      email: input.email,
      password: input.password,
      role: input.role,
      public_alias: input.public_alias,
    },
  })
}

export async function logout(): Promise<void> {
  await requestJson('/api/auth/logout/', { method: 'POST' })
}

export async function fetchMe(signal?: AbortSignal): Promise<User> {
  const payload = await requestJson('/api/auth/me/', { signal })
  if (payload === null) {
    throw new Error('Resposta vazia ao carregar o usuário.')
  }
  return decodeUser(payload)
}

export async function fetchWsTicket(): Promise<WsTicket> {
  const payload = await requestWithSlashFallback('/api/auth/ws-ticket', { method: 'POST' })
  if (payload === null) {
    throw new Error('Ticket de WebSocket não retornado.')
  }
  return decodeWsTicket(payload)
}
