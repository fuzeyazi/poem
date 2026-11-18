import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import PoemDetail from '@/views/PoemDetail.vue'
import { useUserStore } from '@/store/user'
import * as api from '@/api/user'
import * as poetryApi from '@/api/poetry'

vi.mock('@/api/poetry', () => ({ getContentById: vi.fn().mockResolvedValue({ id: 7, title: '锦瑟', writer: '李商隐', dynasty: '唐代', content: '沧海月明珠有泪' }), getPoemByTitle: vi.fn() }))
vi.mock('@/api/user', () => ({ collectPoem: vi.fn(), uncollectPoem: vi.fn(), getCollectIds: vi.fn().mockResolvedValue([]), bookShow: vi.fn(), bookAddPoem: vi.fn() }))
vi.mock('@/utils/request', () => ({ default: { get: vi.fn().mockRejectedValue(new Error('offline')) } }))
const wrappers: ReturnType<typeof mount>[] = []
async function reader() {
  const pinia = createPinia(); setActivePinia(pinia); useUserStore().setLogin('token', 1, 'reader')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/poem/:title', name: 'poem-detail', component: PoemDetail }, { path: '/poetry', name: 'poetry', component: { template: '<div />' } }, { path: '/ai', name: 'ai', component: { template: '<div />' } }] })
  await router.push('/poetry?q=月&page=2'); await router.push({ path: '/poem/锦瑟', query: { id: '7', from: '/poetry?q=月&page=2' } })
  const wrapper = mount({ template: '<RouterView />' }, { attachTo: document.body, global: { plugins: [pinia, router, ElementPlus], stubs: { AppNav: true, PoemCardModal: true, AllusionCard: true } } })
  wrappers.push(wrapper); await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.bookShow).mockResolvedValue([])
  vi.mocked(api.getCollectIds).mockResolvedValue([])
  vi.mocked(poetryApi.getContentById).mockResolvedValue({ id: 7, title: '锦瑟', writer: '李商隐', dynasty: '唐代', content: '沧海月明珠有泪' })
})
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); document.body.innerHTML = '' })
describe('Material reader', () => {
  it('passes title and id to an editable AI context route', async () => {
    const { wrapper, router } = await reader()
    await wrapper.get('.ask').trigger('click'); await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ poemTitle: '锦瑟', poemId: '7' })
  })
  it('prevents duplicate collection while awaiting the server', async () => {
    let resolve!: (value: string) => void
    vi.mocked(api.collectPoem).mockReturnValue(new Promise<string>(r => { resolve = r }))
    const { wrapper } = await reader()
    const button = wrapper.get('[data-testid="collect"]')
    await button.trigger('click')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(api.collectPoem).toHaveBeenCalledTimes(1)
    resolve('ok'); await flushPromises()
    expect(button.attributes('aria-pressed')).toBe('true')
  })
  it('does not let late initial collection ids undo a completed collection', async () => {
    let resolveIds!: (ids: number[]) => void
    vi.mocked(api.getCollectIds).mockReturnValueOnce(new Promise(r => { resolveIds = r }))
    vi.mocked(api.collectPoem).mockResolvedValue('ok')
    const { wrapper } = await reader()
    const button = wrapper.get('[data-testid="collect"]')
    await button.trigger('click'); await flushPromises()
    expect(button.attributes('aria-pressed')).toBe('true')
    resolveIds([]); await flushPromises()
    expect(button.attributes('aria-pressed')).toBe('true')
  })
  it.each(['success', 'failure'] as const)('preserves unrelated saved poems after an early collection %s', async (outcome) => {
    let resolveIds!: (ids: number[]) => void
    vi.mocked(api.getCollectIds).mockReturnValueOnce(new Promise(resolve => { resolveIds = resolve }))
    if (outcome === 'success') vi.mocked(api.collectPoem).mockResolvedValueOnce('ok')
    else vi.mocked(api.collectPoem).mockRejectedValueOnce(new Error('offline'))
    const { wrapper, router } = await reader()
    await wrapper.get('[data-testid="collect"]').trigger('click'); await flushPromises()
    expect(wrapper.get('[data-testid="collect"]').attributes('aria-pressed')).toBe(outcome === 'success' ? 'true' : 'false')
    resolveIds([9]); await flushPromises()
    vi.mocked(poetryApi.getContentById).mockResolvedValueOnce({ id: 9, title: '早发白帝城', writer: '李白', dynasty: '唐代', content: '朝辞白帝彩云间' })
    await router.push('/poem/早发白帝城?id=9'); await flushPromises()
    expect(wrapper.get('[data-testid="collect"]').attributes('aria-pressed')).toBe('true')
  })
  it('preserves initial saved IDs that arrive while a collection write is pending', async () => {
    let resolveIds!: (ids: number[]) => void
    let resolveWrite!: (value: string) => void
    vi.mocked(api.getCollectIds).mockReturnValueOnce(new Promise(resolve => { resolveIds = resolve }))
    vi.mocked(api.collectPoem).mockReturnValueOnce(new Promise(resolve => { resolveWrite = resolve }))
    const { wrapper, router } = await reader()
    await wrapper.get('[data-testid="collect"]').trigger('click')
    resolveIds([9]); await flushPromises()
    resolveWrite('ok'); await flushPromises()
    expect(wrapper.get('[data-testid="collect"]').attributes('aria-pressed')).toBe('true')
    vi.mocked(poetryApi.getContentById).mockResolvedValueOnce({ id: 9, title: '早发白帝城', writer: '李白', dynasty: '唐代', content: '朝辞白帝彩云间' })
    await router.push('/poem/早发白帝城?id=9'); await flushPromises()
    expect(wrapper.get('[data-testid="collect"]').attributes('aria-pressed')).toBe('true')
  })
  it('distinguishes loading, book failure with retry, and an empty book list', async () => {
    let reject!: (error: Error) => void
    vi.mocked(api.bookShow).mockReturnValueOnce(new Promise((_r, r) => { reject = r }))
    const { wrapper } = await reader()
    await wrapper.get('[data-testid="book-picker"]').trigger('click'); await flushPromises()
    expect(document.body.textContent).toContain('正在加载诗集')
    expect(document.body.textContent).not.toContain('还没有诗集')
    reject(new Error('offline')); await flushPromises()
    expect(document.body.querySelector('[data-testid="books-retry"]')).not.toBeNull()
    ;(document.body.querySelector('[data-testid="books-retry"]') as HTMLButtonElement).click(); await flushPromises()
    expect(document.body.textContent).toContain('还没有诗集')
  })
  it('offers native allusion disclosure and returns to the previous search', async () => {
    const { wrapper, router } = await reader()
    const allusion = wrapper.get('button.allusion-mark')
    expect(allusion.attributes('aria-expanded')).toBe('false')
    await allusion.trigger('click')
    expect(allusion.attributes('aria-expanded')).toBe('true')
    await allusion.trigger('keydown', { key: 'Escape' })
    expect(allusion.attributes('aria-expanded')).toBe('false')
    await wrapper.get('[data-testid="reader-back"]').trigger('click'); await new Promise(r => setTimeout(r, 20)); await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/poetry?q=月&page=2')
  })
})
