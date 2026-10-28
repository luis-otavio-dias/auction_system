import { firstString, isJsonObject } from './json'
import type { JsonObject, JsonValue } from './json'

const DEFAULT_API_URL = 'http://localhost:8001'
const AUTH_EXPIRED_EVENT = 'auth:expired'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || DEFAULT_API_URL).replace(/\/+$/, '')

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly detail: string
  readonly fields: Record<string, string[]>
  readonly context: JsonObject

  constructor(
    code: string,
    status: number,
    detail: string,
    fields: Record<string, string[]> = {},
    context: JsonObject = {},
  ) {
    super(detail)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.detail = detail
    this.fields = fields
    this.context = context
  }
}

export interface ApiRequestOptions {
  method?: string
  body?: JsonValue
  signal?: AbortSignal
}

export function isApiError(error: Error): error is ApiError {
  return error instanceof ApiError
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function websocketUrl(path: string, ticket: string | null): string {
  const base = new URL(API_BASE_URL)
  const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  const query = ticket ? `?ticket=${encodeURIComponent(ticket)}` : ''
  return `${protocol}//${base.host}${path}${query}`
}

export function withQuery(path: string, params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      query.set(key, String(value))
    }
  })
  const serialized = query.toString()
  return serialized ? `${path}?${serialized}` : path
}

function fieldErrors(source: JsonObject): Record<string, string[]> {
  const result: Record<string, string[]> = {}
  Object.entries(source).forEach(([key, value]) => {
    if (key === 'code' || key === 'detail' || key === 'message') {
      return
    }
    if (Array.isArray(value)) {
      const messages = value.filter((item): item is string => typeof item === 'string')
      if (messages.length > 0) {
        result[key] = messages
      }
      return
    }
    if (typeof value === 'string') {
      result[key] = [value]
    }
  })
  return result
}

function errorFromResponse(status: number, body: JsonValue | null): ApiError {
  if (isJsonObject(body)) {
    const code = firstString(body, ['code']) ?? 'HTTP_ERROR'
    const fields = fieldErrors(body)
    const detail =
      firstString(body, ['detail', 'message'])
      ?? Object.values(fields).flat()[0]
      ?? `A requisição falhou (${status}).`
    return new ApiError(code, status, detail, fields, body)
  }
  if (typeof body === 'string' && body.trim() !== '') {
    return new ApiError('HTTP_ERROR', status, body)
  }
  return new ApiError('HTTP_ERROR', status, `A requisição falhou (${status}).`)
}

async function readBody(response: Response): Promise<JsonValue | null> {
  if (response.status === 204) {
    return null
  }
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text) as JsonValue
  } catch {
    return text
  }
}

function isAuthEndpoint(path: string): boolean {
  const clean = path.split('?')[0]
  return (
    clean.startsWith('/api/auth/token')
    || clean.startsWith('/api/auth/refresh')
    || clean.startsWith('/api/auth/register')
    || clean.startsWith('/api/auth/logout')
  )
}

function notifySessionExpired(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  }
}

let refreshPromise: Promise<boolean> | null = null

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise
  }
  refreshPromise = (async () => {
    try {
      const response = await fetch(apiUrl('/api/auth/refresh/'), {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      })
      return response.ok
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

async function execute(
  path: string,
  options: ApiRequestOptions,
  allowRefresh: boolean,
): Promise<JsonValue | null> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: options.method ?? 'GET',
      credentials: 'include',
      headers,
      body,
      signal: options.signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiError('NETWORK_ERROR', 0, 'Não foi possível conectar ao servidor.')
  }
  if (response.status === 401 && !isAuthEndpoint(path)) {
    if (allowRefresh && await refreshSession()) {
      return execute(path, options, false)
    }
    notifySessionExpired()
  }
  const parsed = await readBody(response)
  if (!response.ok) {
    throw errorFromResponse(response.status, parsed)
  }
  return parsed
}

export async function requestJson(
  path: string,
  options: ApiRequestOptions = {},
): Promise<JsonValue | null> {
  return execute(path, options, true)
}

export async function requestWithSlashFallback(
  path: string,
  options: ApiRequestOptions = {},
): Promise<JsonValue | null> {
  try {
    return await requestJson(path, options)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404 && !path.endsWith('/')) {
      return requestJson(`${path}/`, options)
    }
    throw error
  }
}

export function isAbortError(error: Error): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
