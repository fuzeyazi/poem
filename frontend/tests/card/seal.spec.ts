import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ClassicalSeal from '@/components/card/ClassicalSeal.vue'

describe('ClassicalSeal 印章组件单元测试', () => {
  it('正确渲染 1 字印章（单字置中）', () => {
    const wrapper = mount(ClassicalSeal, {
      props: {
        text: '静',
        size: 60,
        shape: 'square',
        carving: 'yang'
      }
    })

    const texts = wrapper.findAll('text')
    expect(texts).toHaveLength(1)
    expect(texts[0].text()).toBe('靜') // 默认启用了繁体转换
    expect(texts[0].attributes('x')).toBe('50')
    expect(texts[0].attributes('dominant-baseline')).toBe('central')
  })

  it('正确渲染 2 字印章（单竖列自上而下）', () => {
    const wrapper = mount(ClassicalSeal, {
      props: {
        text: '太白',
        shape: 'square',
        carving: 'yang',
        traditional: false
      }
    })

    const texts = wrapper.findAll('text')
    expect(texts).toHaveLength(2)
    expect(texts[0].text()).toBe('太')
    expect(texts[1].text()).toBe('白')
    expect(texts[0].attributes('x')).toBe('50')
    expect(texts[1].attributes('x')).toBe('50')
    expect(Number(texts[0].attributes('y'))).toBeLessThan(Number(texts[1].attributes('y')))
  })

  it('正确渲染 3 字印章（右列两字，左列一字置中）', () => {
    const wrapper = mount(ClassicalSeal, {
      props: {
        text: '摩诘印',
        shape: 'square',
        carving: 'yang',
        traditional: false
      }
    })

    const texts = wrapper.findAll('text')
    expect(texts).toHaveLength(3)
    expect(texts[0].text()).toBe('摩') // 右上
    expect(texts[1].text()).toBe('诘') // 右下
    expect(texts[2].text()).toBe('印') // 左中
    expect(Number(texts[0].attributes('x'))).toBeGreaterThan(Number(texts[2].attributes('x')))
    expect(texts[0].attributes('x')).toBe(texts[1].attributes('x'))
  })

  it('正确渲染 4 字经典回文印章（自右向左、自上而下 2x2 规矩）', () => {
    const wrapper = mount(ClassicalSeal, {
      props: {
        text: '李白之印',
        shape: 'square',
        carving: 'yang',
        traditional: false
      }
    })

    const texts = wrapper.findAll('text')
    expect(texts).toHaveLength(4)
    // 字符顺序：0:李(右上), 1:白(右下), 2:之(左上), 3:印(左下)
    expect(texts[0].text()).toBe('李')
    expect(texts[1].text()).toBe('白')
    expect(texts[2].text()).toBe('之')
    expect(texts[3].text()).toBe('印')

    const x0 = Number(texts[0].attributes('x'))
    const y0 = Number(texts[0].attributes('y'))
    const x1 = Number(texts[1].attributes('x'))
    const y1 = Number(texts[1].attributes('y'))
    const x2 = Number(texts[2].attributes('x'))
    const y2 = Number(texts[2].attributes('y'))
    const x3 = Number(texts[3].attributes('x'))
    const y3 = Number(texts[3].attributes('y'))

    // 右列 x > 左列 x
    expect(x0).toBeGreaterThan(x2)
    expect(x1).toBeGreaterThan(x3)
    expect(x0).toBe(x1)
    expect(x2).toBe(x3)

    // 上排 y < 下排 y
    expect(y0).toBeLessThan(y1)
    expect(y2).toBeLessThan(y3)
  })

  it('支持白文（阴刻）与朱文（阳刻）刻法切换', () => {
    // 白文 (阴刻)
    const yinWrapper = mount(ClassicalSeal, {
      props: {
        text: '雅赏',
        carving: 'yin',
        paperColor: '#faf6ee'
      }
    })
    // 阴刻底色为满版填实
    const yinRect = yinWrapper.find('rect')
    expect(yinRect.attributes('fill')).toContain('url(#cinnabar-')
    // 阴刻文字填充为纸色
    const yinTexts = yinWrapper.findAll('text')
    expect(yinTexts[0].attributes('fill')).toBe('#faf6ee')

    // 朱文 (阳刻)
    const yangWrapper = mount(ClassicalSeal, {
      props: {
        text: '雅赏',
        carving: 'yang'
      }
    })
    // 阳刻边框描边
    const yangRect = yangWrapper.find('rect')
    expect(yangRect.attributes('stroke')).toContain('url(#cinnabar-')
    expect(yangRect.attributes('fill')).toBe('none')
  })

  it('支持圆形 / 椭圆印形制', () => {
    const ovalWrapper = mount(ClassicalSeal, {
      props: {
        text: '长乐',
        shape: 'oval',
        carving: 'yin'
      }
    })
    expect(ovalWrapper.find('ellipse').exists()).toBe(true)
  })

  it('金石残损噪点滤镜与渐变节点完整', () => {
    const wrapper = mount(ClassicalSeal, {
      props: { text: '墨客' }
    })
    expect(wrapper.find('feTurbulence').exists()).toBe(true)
    expect(wrapper.find('feDisplacementMap').exists()).toBe(true)
    expect(wrapper.find('linearGradient').exists()).toBe(true)
  })
})
