import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { setSystemTheme } from '../test/matchMedia'
import { ThemeProvider } from './ThemeProvider'
import { THEME_STORAGE_KEY, useTheme } from './theme-context'

function ThemeProbe() {
  const { theme, toggleTheme } = useTheme()
  return <button type="button" onClick={toggleTheme}>{theme}</button>
}

function renderTheme() {
  return render(<ThemeProvider><ThemeProbe /></ThemeProvider>)
}

describe('ThemeProvider', () => {
  it('inicia no tema claro quando o sistema prefere claro', () => {
    renderTheme()

    expect(screen.getByRole('button')).toHaveTextContent('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('inicia no tema escuro quando o sistema prefere escuro', () => {
    setSystemTheme('dark')
    renderTheme()

    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('prioriza a preferência salva sobre o sistema', () => {
    setSystemTheme('dark')
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
    renderTheme()

    expect(screen.getByRole('button')).toHaveTextContent('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('alterna o tema e persiste a escolha', async () => {
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button'))

    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('acompanha mudanças do sistema enquanto não há preferência salva', () => {
    renderTheme()

    act(() => setSystemTheme('dark'))

    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('ignora mudanças do sistema depois que uma preferência é salva', async () => {
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button'))
    act(() => setSystemTheme('light'))

    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
