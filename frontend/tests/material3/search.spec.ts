import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'
import PoetryList from '@/views/PoetryList.vue'
import AgeTabs from '@/components/AgeTabs.vue'
import * as api from '@/api/poetry'
import * as userApi from '@/api/user'
import { useUserStore } from '@/store/user'
import appRouter from '@/router'

vi.mock('@/api/poetry', () => ({ getPoetryCount: vi.fn(), getAllDynasty: vi.fn(), getVeryGoodPoem: vi.fn(), getPoemByTitle: vi.fn(), getPoemsByDynasty: vi.fn(), getPoemPage: vi.fn(), getSearchSuggest: vi.fn(), getHotSearch: vi.fn() }))
vi.mock('@/api/writer', () => ({ getWriterCount: vi.fn().mockResolvedValue(0) }))
vi.mock('@/api/rhesis', () => ({ getRhesisCount: vi.fn().mockResolvedValue(0), getRandomRhesis: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/user', () => ({ collectPoem: vi.fn(), uncollectPoem: vi.fn(), getCollectIds: vi.fn().mockResolvedValue([]) }))

const poem = (title: string, id = 1) => ({ id, title, writer: '李白', dynasty: '唐代', content: '床前明月光' })
const wrappers: ReturnType<typeof mount>[] = []
async function page(url = '/poetry', loggedIn = false) {
  const router = createRouter({ history: createMemoryHistory(), scrollBehavior: appRouter.options.scrollBehavior, routes: [{ path: '/poetry', name: 'poetry', component: PoetryList }, { path: '/poem/:title', name: 'poem-detail', component: { template: '<div />' } }, { path: '/ai', component: { template: '<div />' } }] })
  await router.push(url)
  const pinia = createPinia()
  if (loggedIn) useUserStore(pinia).setLogin('token', 1, 'reader')
  const wrapper = mount({ template: '<RouterView />' }, { attachTo: document.body, global: { plugins: [pinia, router], stubs: { AppNav: true, NightRidge: true }, directives: { loading: () => {} } } })
  wrappers.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  vi.stubGlobal('scrollTo', vi.fn())
  vi.mocked(api.getPoetryCount).mockResolvedValue(0)
  vi.mocked(api.getVeryGoodPoem).mockResolvedValue(poem('推荐'))
  vi.mocked(api.getPoemPage).mockResolvedValue({ records: [poem('馆藏')], total: 1 })
  vi.mocked(api.getPoemByTitle).mockResolvedValue({ records: [poem('搜索结果')], total: 12 })
  vi.mocked(api.getPoemsByDynasty).mockResolvedValue({ records: [poem('唐诗')], total: 12 })
  vi.mocked(api.getAllDynasty).mockResolvedValue(['唐代', '宋代'])
  vi.mocked(api.getHotSearch).mockResolvedValue([])
  vi.mocked(api.getSearchSuggest).mockResolvedValue(['静夜思', '静夜'])
  vi.mocked(userApi.getCollectIds).mockResolvedValue([])
})
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.useRealTimers(); vi.unstubAllGlobals() })

describe('Material search', () => {
  it('restores URL filters and page and keeps poem id in native links', async () => {
    const { wrapper } = await page('/poetry?q=月&page=2')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('月')
    expect(api.getPoemByTitle).toHaveBeenCalledWith('月', 2, 4)
    expect(wrapper.get('a.scroll').attributes('href')).toContain('id=1')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('2')
  })
  it('exposes native dynasty chips with a selected state', async () => {
    const wrapper = mount(AgeTabs, { props: { dynasties: ['唐代'], modelValue: '唐代' } })
    wrappers.push(wrapper)
    expect(wrapper.findAll('button.at')).toHaveLength(2)
    expect(wrapper.get('button.on').attributes('aria-pressed')).toBe('true')
    await wrapper.get('button.on').trigger('click')
    expect(wrapper.emitted('change')?.[0]).toEqual(['唐代'])
  })
  it('ignores an older response after a new committed query', async () => {
    let resolveOld!: (value: any) => void
    vi.mocked(api.getPoemByTitle).mockImplementation((q) => q === '旧' ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ records: [poem('新结果')], total: 1 }))
    const { wrapper } = await page()
    await wrapper.get('input').setValue('旧'); await wrapper.get('form').trigger('submit'); await flushPromises()
    await wrapper.get('input').setValue('新'); await wrapper.get('form').trigger('submit'); await flushPromises()
    resolveOld({ records: [poem('旧结果')], total: 1 }); await flushPromises()
    expect(wrapper.text()).toContain('新结果')
    expect(wrapper.text()).not.toContain('旧结果')
  })
  it('retains successful records during refresh failure and retries in place', async () => {
    const { wrapper, router } = await page('/poetry?q=月')
    vi.mocked(api.getPoemByTitle).mockRejectedValueOnce(new Error('offline'))
    await router.push('/poetry?q=风'); await flushPromises()
    expect(wrapper.text()).toContain('搜索结果')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('.empty-state').exists()).toBe(false)
    vi.mocked(api.getPoemByTitle).mockResolvedValueOnce({ records: [poem('重试结果')], total: 1 })
    await wrapper.get('[data-testid="search-retry"]').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('重试结果')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })
  it('does not submit Chinese composition and selects suggestions with arrow and Enter', async () => {
    const { wrapper, router } = await page()
    vi.useFakeTimers()
    const input = wrapper.get('input')
    await input.trigger('compositionstart'); await input.setValue('静'); await input.trigger('keydown', { key: 'Enter', isComposing: true })
    expect(router.currentRoute.value.query.q).toBeUndefined()
    await input.trigger('compositionend'); await vi.advanceTimersByTimeAsync(300); await flushPromises()
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBeTruthy()
    await input.trigger('keydown', { key: 'Enter' }); await flushPromises()
    expect(router.currentRoute.value.query.q).toBe('静夜思')
  })
  it('ignores a pending suggestion when input changes again', async () => {
    const { wrapper } = await page()
    vi.useFakeTimers()
    let resolve!: (value: string[]) => void
    vi.mocked(api.getSearchSuggest).mockReturnValueOnce(new Promise(r => { resolve = r }))
    await wrapper.get('input').setValue('旧'); await vi.advanceTimersByTimeAsync(300)
    await wrapper.get('input').setValue('新')
    resolve(['旧建议']); await flushPromises()
    expect(wrapper.text()).not.toContain('旧建议')
  })
  it('starts ArrowUp at the last suggestion and Escape closes the list', async () => {
    const { wrapper } = await page()
    vi.useFakeTimers()
    const input = wrapper.get('input')
    await input.setValue('静'); await vi.advanceTimersByTimeAsync(300); await flushPromises()
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe('suggestion-1')
    await input.trigger('keydown', { key: 'Escape' })
    expect(input.attributes('aria-expanded')).toBe('false')
  })
  it('treats an infinite URL page as the first page', async () => {
    const { wrapper } = await page('/poetry?dynasty=唐代&page=Infinity')
    expect(api.getPoemsByDynasty).toHaveBeenCalledWith('唐代', 1, 4)
    expect(wrapper.get('[aria-current="page"]').text()).toBe('1')
  })
  it('restores cached search records and scroll immediately when returning from a poem', async () => {
    const { wrapper, router } = await page('/poetry?q=返还&page=2')
    vi.stubGlobal('scrollY', 480)
    await router.push('/poem/搜索结果?id=1'); await flushPromises()
    vi.mocked(api.getPoemByTitle).mockReturnValueOnce(new Promise(() => {}))
    await router.push('/poetry?q=返还&page=2'); await flushPromises()
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('返还')
    expect(wrapper.get('a.scroll').text()).toContain('搜索结果')
    expect(wrapper.get('[aria-current="page"]').text()).toBe('2')
    expect(window.scrollTo).toHaveBeenLastCalledWith({ top: 480 })
  })
  it('keeps retained results when opening a poem after a failed refresh', async () => {
    const { wrapper, router } = await page('/poetry?q=恢复前')
    vi.mocked(api.getPoemByTitle).mockRejectedValueOnce(new Error('offline'))
    await router.push('/poetry?q=恢复错误'); await flushPromises()
    await router.push('/poem/搜索结果?id=1'); await flushPromises()
    vi.mocked(api.getPoemByTitle).mockReturnValueOnce(new Promise(() => {}))
    await router.push('/poetry?q=恢复错误'); await flushPromises()
    expect(wrapper.find('a.scroll').exists()).toBe(true)
    expect(wrapper.get('a.scroll').text()).toContain('搜索结果')
  })
  it.each(['success', 'failure'] as const)('preserves unrelated saved recommendations after an early collection %s', async (outcome) => {
    let resolveIds!: (ids: number[]) => void
    vi.mocked(userApi.getCollectIds).mockReturnValueOnce(new Promise(resolve => { resolveIds = resolve }))
    vi.mocked(api.getVeryGoodPoem).mockResolvedValueOnce(poem('早读', 7))
    if (outcome === 'success') vi.mocked(userApi.collectPoem).mockResolvedValueOnce('ok')
    else vi.mocked(userApi.collectPoem).mockRejectedValueOnce(new Error('offline'))
    const { wrapper } = await page('/poetry', true)
    await wrapper.get('.hero-actions button[aria-pressed]').trigger('click'); await flushPromises()
    expect(wrapper.get('.hero-actions button[aria-pressed]').attributes('aria-pressed')).toBe(outcome === 'success' ? 'true' : 'false')
    resolveIds([9]); await flushPromises()
    vi.mocked(api.getVeryGoodPoem).mockResolvedValueOnce(poem('已收藏', 9))
    await wrapper.get('.featured .sec-head button').trigger('click'); await flushPromises()
    expect(wrapper.get('.hero-actions button[aria-pressed]').attributes('aria-pressed')).toBe('true')
  })
})
