import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import Forum from '@/views/Forum.vue'
import * as forum from '@/api/forum'

vi.mock('@/api/forum', () => ({
  selectTiez: vi.fn(), searchForum: vi.fn(), postBlog: vi.fn(),
  selectXiangxi: vi.fn(), dianzan: vi.fn(), selectComments: vi.fn(),
  postForumComment: vi.fn(), commentDianzan: vi.fn(),
}))
vi.mock('@stomp/stompjs', () => ({ Client: class { activate() {} deactivate() {} } }))

const wrappers: ReturnType<typeof mount>[] = []
async function openForum() {
  const wrapper = mount(Forum, {
    attachTo: document.body,
    global: { plugins: [createPinia(), ElementPlus], stubs: { AppNav: true }, directives: { reveal: () => {} } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  await wrapper.get('.blog-card').trigger('click')
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(forum.selectTiez).mockResolvedValue({ records: [{ id: 1, title: '诗词交流' }], total: 1 } as any)
  vi.mocked(forum.selectXiangxi).mockResolvedValue({ id: 1, title: '诗词交流' } as any)
  vi.mocked(forum.selectComments).mockResolvedValue([{ id: 5, context: '已有评论' }] as any)
  vi.mocked(forum.postForumComment).mockResolvedValue('ok')
})
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  ElMessage.closeAll()
  document.body.innerHTML = ''
})

describe('Forum comment refresh after publishing', () => {
  it('keeps confirmed success and existing comments when the list refresh fails, then retries only the read', async () => {
    const wrapper = await openForum()
    vi.mocked(forum.selectComments).mockRejectedValueOnce(new Error('refresh offline'))
    await wrapper.get('.cm-input input').setValue('新评论')
    await wrapper.get('.cm-input form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('已有评论')
    expect((wrapper.get('.cm-input input').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain('评论失败')
    expect(wrapper.get('[role="alert"]').text()).toContain('评论已提交，列表刷新失败')
    expect(document.body.textContent).toContain('评论成功')

    vi.mocked(forum.selectComments).mockResolvedValueOnce([{ id: 6, context: '新评论' }] as any)
    const retry = wrapper.findAll('button').find(button => button.text().includes('重试加载评论'))!
    await retry.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('新评论')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(forum.postForumComment).toHaveBeenCalledTimes(1)
    expect(forum.selectComments).toHaveBeenCalledTimes(3)
  })

  it('retains the comment and reply target when the write itself fails', async () => {
    const wrapper = await openForum()
    await wrapper.findAll('button').find(button => button.text() === '回复')!.trigger('click')
    vi.mocked(forum.postForumComment).mockRejectedValueOnce(new Error('write offline'))
    await wrapper.get('.cm-input input').setValue('回复草稿')
    await wrapper.get('.cm-input form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.cm-input [role="alert"]').text()).toContain('评论失败')
    expect((wrapper.get('.cm-input input').element as HTMLInputElement).value).toBe('回复草稿')
    expect(wrapper.find('.replying').exists()).toBe(true)
    expect(forum.selectComments).toHaveBeenCalledTimes(1)
  })
})
