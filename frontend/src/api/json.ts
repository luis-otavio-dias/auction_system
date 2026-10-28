export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export type JsonObject = { [key: string]: JsonValue }

export class DecodeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DecodeError'
  }
}

export function isJsonObject(value: JsonValue | undefined): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function expectObject(value: JsonValue | undefined, context: string): JsonObject {
  if (!isJsonObject(value)) {
    throw new DecodeError(`Resposta inválida para ${context}.`)
  }
  return value
}

export function expectArray(value: JsonValue | undefined, context: string): JsonValue[] {
  if (!Array.isArray(value)) {
    throw new DecodeError(`Lista inválida para ${context}.`)
  }
  return value
}

export function expectString(value: JsonValue | undefined, context: string): string {
  if (typeof value !== 'string') {
    throw new DecodeError(`Texto inválido para ${context}.`)
  }
  return value
}

export function expectNumber(value: JsonValue | undefined, context: string): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }
  throw new DecodeError(`Número inválido para ${context}.`)
}

export function expectBoolean(value: JsonValue | undefined, context: string): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  throw new DecodeError(`Booleano inválido para ${context}.`)
}

export function optionalString(value: JsonValue | undefined): string | null {
  return typeof value === 'string' ? value : null
}

export function optionalNumber(value: JsonValue | undefined): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return null
}

export function optionalBoolean(value: JsonValue | undefined): boolean | null {
  return typeof value === 'boolean' ? value : null
}

export function field(source: JsonObject, key: string): JsonValue | undefined {
  return source[key]
}

export function textField(source: JsonObject, key: string, fallback = ''): string {
  return optionalString(source[key]) ?? fallback
}

export function numberField(source: JsonObject, key: string, fallback = 0): number {
  return optionalNumber(source[key]) ?? fallback
}

export function booleanField(source: JsonObject, key: string, fallback = false): boolean {
  return optionalBoolean(source[key]) ?? fallback
}

export function decimalField(source: JsonObject, key: string, fallback = '0.00'): string {
  const value = source[key]
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  return fallback
}

export function optionalDecimal(source: JsonObject, key: string): string | null {
  const value = source[key]
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  return null
}

export function stringList(source: JsonObject, key: string): string[] {
  const value = source[key]
  if (typeof value === 'string') {
    return value.trim() === '' ? [] : [value]
  }
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

export function objectField(source: JsonObject, key: string): JsonObject {
  const value = source[key]
  return isJsonObject(value) ? value : {}
}

export function firstObject(source: JsonObject, keys: readonly string[]): JsonObject | null {
  for (const key of keys) {
    const value = source[key]
    if (isJsonObject(value)) {
      return value
    }
  }
  return null
}

export function firstString(source: JsonObject, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string') {
      return value
    }
  }
  return null
}

export function firstNumber(source: JsonObject, keys: readonly string[]): number | null {
  for (const key of keys) {
    const value = optionalNumber(source[key])
    if (value !== null) {
      return value
    }
  }
  return null
}
