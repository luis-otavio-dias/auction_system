export const money = (value: string | number) => {
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) {
    return '0,00'
  }
  return amount.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export const clock = (seconds: number) => {
  const s = Math.max(0, seconds)
  return `${String(Math.floor(s / 3600)).padStart(2, '0')}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m ${String(s % 60).padStart(2, '0')}s`
}

export const parseAmount = (value: string): number | null => {
  const clean = value.replace(/[R$\s]/g, '')
  if (!clean) {
    return null
  }
  const normalized = clean.includes(',')
    ? clean.replace(/\./g, '').replace(',', '.')
    : clean
  const amount = Number(normalized)
  return Number.isFinite(amount) ? amount : null
}

export const dateTime = (value: string | null) => {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export const dateOnly = (value: string | null) => {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return date.toLocaleDateString('pt-BR', { dateStyle: 'long' })
}

export const shortHash = (value: string) => value ? `${value.slice(0, 10)}…${value.slice(-6)}` : '—'

export const statusLabel = (status: string) => {
  if (status === 'live') {
    return 'Ao vivo'
  }
  if (status === 'scheduled') {
    return 'Programado'
  }
  if (status === 'cancelled') {
    return 'Cancelado'
  }
  return 'Encerrado'
}
