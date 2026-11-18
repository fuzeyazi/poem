import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

describe('shared theme', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    document.documentElement.className = 'dark'
  })
  afterEach(() => vi.restoreAllMocks())

  it('starts light without a saved preference and removes the previous dark class', async () => {
    const { useTheme } = await import('@/composables/useTheme')
    expect(useTheme().theme.value).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('light')
  })

  it('restores dark and toggles both shared consumers, document colors, and persistence', async () => {
    localStorage.setItem('poetry-theme', 'dark')
    const { useTheme } = await import('@/composables/useTheme')
    const first = useTheme()
    const second = useTheme()
    expect(second.theme.value).toBe('dark')
    first.toggleTheme()
    expect(second.theme.value).toBe('light')
    expect(localStorage.getItem('poetry-theme')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    second.toggleTheme()
    expect(first.theme.value).toBe('dark')
    expect(localStorage.getItem('poetry-theme')).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('ignores invalid saved values', async () => {
    localStorage.setItem('poetry-theme', 'midnight')
    const { useTheme } = await import('@/composables/useTheme')
    expect(useTheme().theme.value).toBe('light')
  })

  it('still toggles if browser storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const { useTheme } = await import('@/composables/useTheme')
    const { theme, toggleTheme } = useTheme()
    expect(() => toggleTheme()).not.toThrow()
    expect(theme.value).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
