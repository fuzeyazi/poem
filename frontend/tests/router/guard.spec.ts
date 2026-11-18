import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '@/router'
import { useUserStore } from '@/store/user'

describe('路由守卫与兜底路由', () => {
  beforeEach(() => {
    vi.stubGlobal('scrollTo', vi.fn())
    setActivePinia(createPinia())
    useUserStore().clearToken()
  })

  afterEach(() => vi.unstubAllGlobals())

  it('未登录访问受保护页面 → 重定向登录页并携带 redirect', async () => {
    await router.push('/poetry')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/poetry')
  })

  it('未知路径 → 404 兜底页（无需登录）', async () => {
    await router.push('/no/such/page')
    expect(router.currentRoute.value.name).toBe('not-found')
  })

  it('已登录访问受保护页面 → 放行', async () => {
    useUserStore().setLogin('t', 1, 'u')
    await router.push('/poetry')
    expect(router.currentRoute.value.name).toBe('poetry')
  })
})
