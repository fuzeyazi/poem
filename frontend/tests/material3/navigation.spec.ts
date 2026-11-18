import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent } from 'vue'
import AppNav from '@/components/AppNav.vue'
import App from '@/App.vue'
import { useUserStore } from '@/store/user'

vi.mock('@/api/user', () => ({ getRemindCount: async () => ({ count: 104 }) }))
vi.mock('@/utils/reviewRemind', () => ({ setupReviewRemind: () => {} }))
vi.mock('@/components/soundscape/SoundscapeWidget.vue', () => ({ default: { template: '<div />' } }))

let compact = true
let wrapper: VueWrapper | undefined
beforeEach(() => {
  compact = true
  vi.stubGlobal('matchMedia', () => ({
    matches: compact, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  // jsdom lacks the browser's dialog implementation; retain real component focus handling.
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

async function render(path = '/poetry', signedIn = false) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/poetry', '/poem/:title', '/writers', '/rhesis', '/review', '/forum', '/ai', '/notice', '/center', '/console', '/login']
      .map((path) => ({ path, component: { template: '<main />' } })),
  })
  const pinia = createPinia()
  if (signedIn) useUserStore(pinia).setLogin('existing-token', 7, '读者')
  await router.push(path)
  await router.isReady()
  wrapper = mount(AppNav, { attachTo: document.body, global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router, store: useUserStore(pinia) }
}

describe('responsive navigation', () => {
  it.each([false, true])('skip link bypasses navigation and starts page keyboard order (compact=%s)', async (mobile) => {
    compact = mobile
    const page = defineComponent({
      components: { AppNav },
      template: '<section><AppNav /><button type="button" data-page-control>阅读正文</button></section>',
    })
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/poetry', component: page },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ] })
    await router.push('/poetry')
    await router.isReady()
    wrapper = mount(App, { attachTo: document.body, global: { plugins: [createPinia(), router] } })
    await flushPromises()
    const target = wrapper.get('#main-content').element as HTMLElement
    // The browser's next Tab starts at the first following focusable element in DOM order.
    target.focus()
    const nextControl = Array.from(document.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), [tabindex="0"]'))
      .find((element) => target.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING)
    expect(nextControl).toBe(wrapper.get('[data-page-control]').element)
    const skip = wrapper.get('.skip-link')
    ;(skip.element as HTMLElement).focus()
    await skip.trigger('click')
    expect(document.activeElement).toBe(target)
  })

  it('opens the mobile modal, traps focus, and returns focus on Escape', async () => {
    const { wrapper } = await render()
    const trigger = wrapper.get('button[aria-controls="primary-navigation-drawer"]')
    ;(trigger.element as HTMLButtonElement).focus()
    await trigger.trigger('click')
    const dialog = wrapper.get('dialog')
    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(dialog.attributes('aria-modal')).toBe('true')
    const controls = dialog.findAll('button, a[href]')
    expect(document.activeElement).toBe(controls[0].element)
    ;(controls.at(-1)!.element as HTMLElement).focus()
    await controls.at(-1)!.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(controls[0].element)
    await controls[0].trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(controls.at(-1)!.element)
    await dialog.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('dialog').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('closes the drawer after navigation and marks the current destination', async () => {
    const { wrapper, router } = await render()
    await wrapper.get('button[aria-controls="primary-navigation-drawer"]').trigger('click')
    await wrapper.get('a[href="/writers"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/writers')
    expect(wrapper.find('dialog').exists()).toBe(false)
    await wrapper.get('button[aria-controls="primary-navigation-drawer"]').trigger('click')
    expect(wrapper.get('a[href="/writers"]').attributes('aria-current')).toBe('page')
  })

  it('allows the backdrop to dismiss the mobile drawer', async () => {
    const { wrapper } = await render()
    await wrapper.get('button[aria-controls="primary-navigation-drawer"]').trigger('click')
    await wrapper.get('dialog').trigger('click')
    expect(wrapper.find('dialog').exists()).toBe(false)
  })

  it('uses a single desktop navigation, associates poem detail with poetry, and preserves account actions', async () => {
    compact = false
    const { wrapper, router, store } = await render('/poem/静夜思', true)
    expect(wrapper.findAll('nav')).toHaveLength(1)
    expect(wrapper.find('dialog').exists()).toBe(false)
    expect(wrapper.find('button[aria-controls="primary-navigation-drawer"]').exists()).toBe(false)
    expect(wrapper.get('nav a[href="/poetry"]').attributes('aria-current')).toBe('page')
    expect(wrapper.get('a[href="/review"]').text()).toContain('99+')
    await wrapper.get('button[data-action="logout"]').trigger('click')
    await flushPromises()
    expect(store.token).toBe('')
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
