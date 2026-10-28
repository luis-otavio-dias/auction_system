import { vi } from 'vitest'

type ThemeListener = (event: MediaQueryListEvent) => void

let prefersDark = false
const listeners = new Set<ThemeListener>()

export const matchMediaMock = vi.fn((query: string) => ({
  get matches() {
    return query === '(prefers-color-scheme: dark)' ? prefersDark : false
  },
  media: query,
  onchange: null,
  addEventListener: (type: string, listener: ThemeListener) => {
    if (type === 'change') listeners.add(listener)
  },
  removeEventListener: (type: string, listener: ThemeListener) => {
    if (type === 'change') listeners.delete(listener)
  },
  addListener: (listener: ThemeListener) => listeners.add(listener),
  removeListener: (listener: ThemeListener) => listeners.delete(listener),
  dispatchEvent: () => true,
}) as MediaQueryList)

export function setSystemTheme(theme: 'light' | 'dark') {
  prefersDark = theme === 'dark'
  const event = { matches: prefersDark, media: '(prefers-color-scheme: dark)' } as MediaQueryListEvent
  listeners.forEach(listener => listener(event))
}

export function resetMatchMedia() {
  prefersDark = false
  listeners.clear()
  matchMediaMock.mockClear()
}
