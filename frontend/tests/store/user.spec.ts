import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUserStore } from '@/store/user'

describe('user store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('setLogin 写入登录态', () => {
    const s = useUserStore()
    s.setLogin('jwt-token', 42, '青莲')
    expect(s.token).toBe('jwt-token')
    expect(s.userId).toBe(42)
    expect(s.userName).toBe('青莲')
  })

  it('clearToken 清空登录态', () => {
    const s = useUserStore()
    s.setLogin('jwt-token', 42, '青莲')
    s.clearToken()
    expect(s.token).toBe('')
    expect(s.userId).toBeNull()
    expect(s.userName).toBe('')
  })
})
