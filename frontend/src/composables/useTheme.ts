import { readonly, shallowRef } from 'vue'

const theme = shallowRef<'light' | 'dark'>('light')
let initialized = false

function applyTheme() {
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
  document.documentElement.style.colorScheme = theme.value
}

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  applyTheme()
  try {
    localStorage.setItem('poetry-theme', theme.value)
  } catch {
    // A blocked storage policy must not prevent the current session from changing theme.
  }
}

export function useTheme() {
  if (!initialized && typeof document !== 'undefined') {
    try {
      theme.value = localStorage.getItem('poetry-theme') === 'dark' ? 'dark' : 'light'
    } catch {
      theme.value = 'light'
    }
    applyTheme()
    initialized = true
  }
  return { theme: readonly(theme), toggleTheme }
}
