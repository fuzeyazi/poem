import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import Login from '@/views/Login.vue'
import Feedback from '@/views/Feedback.vue'
import Forum from '@/views/Forum.vue'
import UserCenter from '@/views/UserCenter.vue'
import AdminCrud from '@/components/AdminCrud.vue'
import Console from '@/views/Console.vue'
import * as admin from '@/api/adminApi'
import * as user from '@/api/user'
import * as feedback from '@/api/feedback'
import * as forum from '@/api/forum'

vi.mock('@/api/user', () => ({ login: vi.fn(), register: vi.fn(), getMessageById: vi.fn().mockResolvedValue({ name: '读者', email: 'reader@example.com' }), updateMessageById: vi.fn(), getCollectPoems: vi.fn().mockResolvedValue([]), getCollectRhesis: vi.fn().mockResolvedValue([]), bookShow: vi.fn().mockResolvedValue([]), bookAdd: vi.fn(), bookShowPoem: vi.fn(), bookStartReview: vi.fn(), bookShowPlan: vi.fn(), bookToday: vi.fn(), reciteDone: vi.fn() }))
vi.mock('@/api/feedback', () => ({ addFeedback: vi.fn(), getAllFeedBack: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/forum', () => ({ selectTiez: vi.fn().mockResolvedValue({ records: [{ id: 1, title: '诗词交流' }], total: 1 }), searchForum: vi.fn(), postBlog: vi.fn(), selectXiangxi: vi.fn().mockResolvedValue({ id: 1, title: '诗词交流' }), dianzan: vi.fn(), selectComments: vi.fn().mockResolvedValue([]), postForumComment: vi.fn(), commentDianzan: vi.fn() }))
vi.mock('@stomp/stompjs', () => ({ Client: class { activate() {} deactivate() {} } }))
vi.mock('@/api/adminApi', () => ({ adminGetCode: vi.fn().mockResolvedValue({ code: '', codeKey: 'captcha-key' }), adminLogin: vi.fn(), reviewList: vi.fn(), reviewDetail: vi.fn(), reviewApprove: vi.fn(), reviewReject: vi.fn(), costReport: vi.fn(), auditList: vi.fn() }))
const wrappers: ReturnType<typeof mount>[] = []
async function page(component: any, props: Record<string, any> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component }, { path: '/poetry', component: { template: '<div />' } }] })
  await router.push('/')
  const wrapper = mount(component, { props, attachTo: document.body, global: { plugins: [createPinia(), router, ElementPlus], stubs: { AppNav: true }, directives: { reveal: () => {} } } })
  wrappers.push(wrapper); await flushPromises()
  return wrapper
}
function pending<T>() {
  let resolve!: (value: T) => void; let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
async function clickText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find(b => b.text().replace(/\s/g, '').includes(text))
  if (!button) throw new Error(`Missing button: ${text}`)
  await button.trigger('click'); await flushPromises()
}
async function submitForm(wrapper: ReturnType<typeof mount>, selector: string) {
  await wrapper.get(selector).trigger('submit'); await flushPromises()
}
beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); ElMessage.closeAll(); document.body.innerHTML = '' })

describe('Material form feedback', () => {
  it('guards operator login, labels each field, and preserves a failed credential draft', async () => {
    const request = pending<any>(); vi.mocked(admin.adminLogin).mockReturnValue(request.promise)
    const wrapper = await page(Console)
    await submitForm(wrapper, '.auth-form')
    expect(wrapper.get('[role="alert"]').text()).toContain('账号、密码与验证码必填')
    expect(admin.adminLogin).not.toHaveBeenCalled()
    const inputs = wrapper.findAll('.auth-form input')
    for (const label of wrapper.findAll('.auth-form label')) expect(label.attributes('for')).toBeTruthy()
    await inputs[0].setValue('operator'); await inputs[1].setValue('secret'); await inputs[2].setValue('1234')
    await submitForm(wrapper, '.auth-form'); await submitForm(wrapper, '.auth-form')
    expect(admin.adminLogin).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.auth-submit-btn').attributes('disabled')).toBeDefined()
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('登录失败')
    expect((inputs[1].element as HTMLInputElement).value).toBe('secret')
  })
  it('uses native keyboard controls for forum categories and collection filters', async () => {
    const wrapper = await page(Forum)
    const categories = wrapper.findAll('button.cat')
    expect(categories).toHaveLength(6)
    expect(categories[0].attributes('aria-pressed')).toBe('true')
    await categories[1].trigger('click'); await flushPromises()
    expect(forum.selectTiez).toHaveBeenLastCalledWith(2, 1, 4)
    expect(categories[1].attributes('aria-pressed')).toBe('true')
    const profile = await page(UserCenter)
    await profile.get('#tab-collect').trigger('click')
    const filter = profile.get('.sub-tabs button:last-child')
    await filter.trigger('click')
    expect(filter.attributes('aria-pressed')).toBe('true')
    expect(profile.text()).toContain('尚无收藏名句')
  })
  it('guards admin saving and keeps a failed record in its dialog without duplicate toast', async () => {
    const request = pending<string>(); const add = vi.fn().mockReturnValue(request.promise)
    const wrapper = await page(AdminCrud, { list: vi.fn().mockResolvedValue({ records: [], total: 0 }), columns: [], formFields: [{ prop: 'title', label: '标题' }], add })
    await clickText(wrapper, '新增条目'); await wrapper.get('.el-dialog input').setValue('原始记录')
    await clickText(wrapper, '保存提交'); await submitForm(wrapper, '.el-dialog form')
    expect(add).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('保存失败')
    expect((wrapper.get('.el-dialog input').element as HTMLInputElement).value).toBe('原始记录')
    expect(document.body.querySelectorAll('.el-message--error')).toHaveLength(0)
  })
  it('shows login field errors on keyboard form submission without a request', async () => {
    const wrapper = await page(Login)
    await submitForm(wrapper, 'form')
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入用户名'))
    expect(wrapper.text()).toContain('请输入密码')
    expect(wrapper.findAll('.el-form-item.is-error')).toHaveLength(2)
    expect(user.login).not.toHaveBeenCalled()
  })
  it('guards pending login and keeps the failed draft and inline server error', async () => {
    const request = pending<any>(); vi.mocked(user.login).mockReturnValue(request.promise)
    const wrapper = await page(Login)
    const inputs = wrapper.findAll('input'); await inputs[0].setValue('reader'); await inputs[1].setValue('secret')
    await submitForm(wrapper, 'form'); await submitForm(wrapper, 'form')
    expect(user.login).toHaveBeenCalledTimes(1)
    expect(wrapper.get('button.submit-btn').attributes('disabled')).toBeDefined()
    request.reject(new Error('offline')); await flushPromises()
    expect((inputs[1].element as HTMLInputElement).value).toBe('secret')
    expect(wrapper.get('[role="alert"]').text()).toContain('登录失败')
    expect(document.body.querySelectorAll('.el-message--error')).toHaveLength(0)
  })
  it('validates optional registration email and prevents duplicate registration', async () => {
    const request = pending<string>(); vi.mocked(user.register).mockReturnValue(request.promise)
    const wrapper = await page(Login)
    await wrapper.get('#tab-register').trigger('click')
    const inputs = wrapper.findAll('#pane-register input')
    await inputs[0].setValue('reader'); await inputs[1].setValue('secret'); await inputs[3].setValue('invalid')
    await submitForm(wrapper, '#pane-register form')
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入有效邮箱')); expect(user.register).not.toHaveBeenCalled()
    await inputs[3].setValue('reader@example.com')
    await submitForm(wrapper, '#pane-register form'); await submitForm(wrapper, '#pane-register form')
    expect(user.register).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('#pane-register [role="alert"]').text()).toContain('注册失败')
    expect((inputs[0].element as HTMLInputElement).value).toBe('reader')
  })
  it('validates feedback and preserves a failed pending submission', async () => {
    const request = pending<string>(); vi.mocked(feedback.addFeedback).mockReturnValue(request.promise)
    const wrapper = await page(Feedback)
    await clickText(wrapper, '提交'); expect(wrapper.find('.el-form-item.is-error').exists()).toBe(true)
    await wrapper.get('textarea').setValue(' 建议保留阅读进度 ')
    await clickText(wrapper, '提交'); await submitForm(wrapper, 'form')
    expect(feedback.addFeedback).toHaveBeenCalledTimes(1)
    expect(feedback.addFeedback).toHaveBeenCalledWith({ message: '建议保留阅读进度' })
    request.reject(new Error('offline')); await flushPromises()
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toContain('建议保留阅读进度')
    expect(wrapper.get('[role="alert"]').text()).toContain('提交失败')
  })
  it('clears feedback only after a successful response', async () => {
    const request = pending<string>(); vi.mocked(feedback.addFeedback).mockReturnValue(request.promise)
    const wrapper = await page(Feedback); await wrapper.get('textarea').setValue('阅读建议'); await clickText(wrapper, '提交')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('阅读建议')
    request.resolve('ok'); await flushPromises()
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
  it('validates post fields, guards pending publishing, and retains a failed draft', async () => {
    const request = pending<any>(); vi.mocked(forum.postBlog).mockReturnValue(request.promise)
    const wrapper = await page(Forum); await clickText(wrapper, '发帖')
    await wrapper.getComponent({ name: 'ElDialog' }).vm.$nextTick()
    const forms = wrapper.findAll('form'); await forms[0].trigger('submit'); await flushPromises()
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入标题')); expect(wrapper.text()).toContain('请输入内容')
    await wrapper.get('.el-dialog input').setValue('春日'); await wrapper.get('.el-dialog textarea').setValue('春日诗词交流')
    await forms[0].trigger('submit'); await flushPromises(); await forms[0].trigger('submit'); await flushPromises()
    expect(forum.postBlog).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('发布失败')
    expect((wrapper.get('.el-dialog textarea').element as HTMLTextAreaElement).value).toBe('春日诗词交流')
  })
  it('guards comment submission and preserves the failed comment', async () => {
    const request = pending<any>(); vi.mocked(forum.postForumComment).mockReturnValue(request.promise)
    const wrapper = await page(Forum); await wrapper.get('.blog-card').trigger('click'); await flushPromises()
    await wrapper.get('.cm-input input').setValue('读后感')
    await clickText(wrapper, '发表'); await submitForm(wrapper, '.cm-input form')
    expect(forum.postForumComment).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('.cm-input [role="alert"]').text()).toContain('评论失败')
    expect((wrapper.get('.cm-input input').element as HTMLInputElement).value).toBe('读后感')
  })
  it('validates profile email, guards saving, and retains the failed edit', async () => {
    const request = pending<string>(); vi.mocked(user.updateMessageById).mockReturnValue(request.promise)
    const wrapper = await page(UserCenter); await clickText(wrapper, '编辑')
    const inputs = wrapper.findAll('.el-dialog input'); await inputs[3].setValue('invalid')
    await submitForm(wrapper, '.el-dialog form'); expect(user.updateMessageById).not.toHaveBeenCalled()
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入有效邮箱'))
    await inputs[3].setValue('reader@example.com')
    await submitForm(wrapper, '.el-dialog form'); await submitForm(wrapper, '.el-dialog form')
    expect(user.updateMessageById).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('保存失败')
  })
  it('validates book title, guards creation, and retains a failed book draft', async () => {
    const request = pending<string>(); vi.mocked(user.bookAdd).mockReturnValue(request.promise)
    const wrapper = await page(UserCenter); await wrapper.get('#tab-book').trigger('click'); await clickText(wrapper, '新建诗集')
    await submitForm(wrapper, '.el-dialog form'); await vi.waitFor(() => expect(wrapper.text()).toContain('请输入诗集名称'))
    await wrapper.get('.el-dialog input').setValue('唐诗选')
    await submitForm(wrapper, '.el-dialog form'); await submitForm(wrapper, '.el-dialog form')
    expect(user.bookAdd).toHaveBeenCalledTimes(1)
    request.reject(new Error('offline')); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('创建失败')
    expect((wrapper.get('.el-dialog input').element as HTMLInputElement).value).toBe('唐诗选')
  })
})
