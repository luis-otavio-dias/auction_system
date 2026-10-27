export const money = (value: number) => value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const clock = (seconds: number) => {
  const s = Math.max(0, seconds)
  return `${String(Math.floor(s / 3600)).padStart(2, '0')}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m ${String(s % 60).padStart(2, '0')}s`
}
