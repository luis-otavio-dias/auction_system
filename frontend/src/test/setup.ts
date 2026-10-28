import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

Object.defineProperty(window, 'scrollTo', { value: vi.fn(), writable: true })
