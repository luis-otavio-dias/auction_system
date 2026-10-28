import { vi } from 'vitest'
import { isJsonObject } from '../api/json'
import type { JsonValue } from '../api/json'

export interface MockReply {
  status?: number
  body?: JsonValue
}

export type FetchHandler = (url: string, init: RequestInit) => MockReply | Promise<MockReply>

export interface FetchCall {
  url: string
  method: string
  body: string | null
  credentials: string | null
}

export function jsonReply(body: JsonValue, status = 200): MockReply {
  return { status, body }
}

export function installFetch(handler: FetchHandler): FetchCall[] {
  const calls: FetchCall[] = []
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const method = init?.method ?? 'GET'
    calls.push({ url, method, body: typeof init?.body === 'string' ? init.body : null, credentials: init?.credentials ?? null })
    const reply = await handler(url, init ?? {})
    const status = reply.status ?? 200
    if (status === 204 || reply.body === undefined) {
      return new Response(null, { status })
    }
    return new Response(JSON.stringify(reply.body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', mock)
  return calls
}

export function queryParam(url: string, key: string): string | null {
  return new URL(url).searchParams.get(key)
}

export function requestBody(call: FetchCall): Record<string, JsonValue> {
  if (call.body === null) {
    return {}
  }
  const parsed = JSON.parse(call.body) as JsonValue
  return isJsonObject(parsed) ? parsed : {}
}

export class MockWebSocket {
  static instances: MockWebSocket[] = []
  readonly url: string
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  closeCode: number | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close(code = 1000): void {
    this.closeCode = code
  }

  emitOpen(): void {
    this.onopen?.(new Event('open'))
  }

  emitMessage(payload: JsonValue): void {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
  }

  emitClose(code = 1006): void {
    this.onclose?.(new CloseEvent('close', { code }))
  }
}
