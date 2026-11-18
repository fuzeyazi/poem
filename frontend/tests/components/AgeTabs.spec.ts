import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AgeTabs from '@/components/AgeTabs.vue'

describe('AgeTabs', () => {
  const dynasties = ['唐代', '宋代']

  it('渲染全部朝代与「全部」项', () => {
    const w = mount(AgeTabs, { props: { dynasties, modelValue: '' } })
    const items = w.findAll('.at')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toBe('全部')
    expect(items[1].text()).toBe('唐代')
  })

  it('当前选中项带 on 类', () => {
    const w = mount(AgeTabs, { props: { dynasties, modelValue: '宋代' } })
    const on = w.findAll('.at').filter((i) => i.classes().includes('on'))
    expect(on).toHaveLength(1)
    expect(on[0].text()).toBe('宋代')
  })

  it('点击朝代触发 update:modelValue 与 change 事件', async () => {
    const w = mount(AgeTabs, { props: { dynasties, modelValue: '' } })
    await w.findAll('.at')[1].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual(['唐代'])
    expect(w.emitted('change')![0]).toEqual(['唐代'])
  })
})
