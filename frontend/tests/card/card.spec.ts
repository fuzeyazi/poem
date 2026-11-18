import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import { toTraditional, stripPunctuation, splitVerseColumns } from '@/utils/s2tDict'
import { formatCardFilename } from '@/utils/cardExporter'
import PoemCardRenderer from '@/components/card/PoemCardRenderer.vue'
import PoemCardModal from '@/components/card/PoemCardModal.vue'

describe('s2tDict 繁简转换与排版辅助工具', () => {
  it('正确将常见诗词字符转换为繁体正字', () => {
    const simplified = '风月梦云归寻独肠别泪绿红细语谁识'
    const traditional = toTraditional(simplified)
    expect(traditional).toBe('風月夢雲歸尋獨腸別淚綠紅細語誰識')
  })

  it('正确剔除全半角古汉语标点符号', () => {
    const raw = '床前明月光，疑是地上霜。举头望明月，低头思故乡！'
    const stripped = stripPunctuation(raw)
    expect(stripped).toBe('床前明月光疑是地上霜举头望明月低头思故乡')
  })

  it('分列算法支持去标点与繁体转换', () => {
    const content = '春江潮水连海平，海上明月共潮生。\n滟滟随波千万里，何处春江无月明！'
    const columns = splitVerseColumns(content, true, true)
    expect(columns).toHaveLength(2)
    // 检查繁体转换与标点剔除
    expect(columns[0]).toBe('春江潮水連海平海上明月共潮生')
    expect(columns[1]).toBe('灩灩隨波千萬里何處春江無月明')
  })
})

describe('cardExporter 文件名与导出工具', () => {
  it('格式化安全的文件名并过滤非法字符', () => {
    const filename = formatCardFilename('李白/杜甫:诗仙*?', '静夜思\\月下独酌<>|')
    expect(filename).toBe('诗词卡片-李白杜甫诗仙-静夜思月下独酌.png')
  })

  it('缺失作者或标题时使用兜底名称', () => {
    const filename = formatCardFilename('', '')
    expect(filename).toBe('诗词卡片-佚名-无题.png')
  })
})

describe('PoemCardRenderer 竖排卡片渲染器', () => {
  const samplePoem = {
    title: '静夜思',
    dynasty: '唐',
    writer: '李白',
    type: '五言绝句',
    content: '床前明月光，疑是地上霜。\n举头望明月，低头思故乡。'
  }

  it('成功挂载并展示古典标题、诗句与落款', () => {
    const wrapper = mount(PoemCardRenderer, {
      props: {
        poem: samplePoem,
        theme: 'xuan',
        traditional: true,
        removePunctuation: true
      }
    })

    // 诗题（繁体 静夜思 -> 靜夜思）
    expect(wrapper.find('.poem-title').text()).toBe('靜夜思')

    // 诗句列
    const verseCols = wrapper.findAll('.verse-column')
    expect(verseCols.length).toBeGreaterThanOrEqual(2)

    // 款识落款（保留分隔点与格式）
    expect(wrapper.find('.colophon-line').text()).toContain('唐·李白 詩')

    // 包含了印章组件
    const seals = wrapper.findAllComponents({ name: 'ClassicalSeal' })
    expect(seals.length).toBeGreaterThanOrEqual(1)
  })

  it('正确切换三大古典主题样式类名', async () => {
    const wrapper = mount(PoemCardRenderer, {
      props: {
        poem: samplePoem,
        theme: 'dark'
      }
    })
    expect(wrapper.classes()).toContain('theme-dark')

    await wrapper.setProps({ theme: 'grid' })
    expect(wrapper.classes()).toContain('theme-grid')

    await wrapper.setProps({ theme: 'xuan' })
    expect(wrapper.classes()).toContain('theme-xuan')
  })
})

describe('PoemCardModal 卡片弹窗交互组件', () => {
  let pinia: any

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  const samplePoem = {
    title: '春晓',
    dynasty: '唐',
    writer: '孟浩然',
    type: '五言绝句',
    content: '春眠不觉晓，处处闻啼鸟。\n夜来风雨声，花落知多少。'
  }

  it('正确接收 visible 与 poem 属性并渲染内部控制台', async () => {
    const wrapper = mount(PoemCardModal, {
      props: {
        visible: true,
        poem: samplePoem
      },
      global: {
        plugins: [pinia, ElementPlus]
      },
      attachTo: document.body
    })

    const { nextTick } = await import('vue')
    await nextTick()

    const preview = document.body.querySelector('.preview-panel')
    expect(preview).not.toBeNull()
    const controls = document.body.querySelector('.controls-panel')
    expect(controls).not.toBeNull()
    const exportBtn = document.body.querySelector('.export-btn')
    expect(exportBtn).not.toBeNull()
    wrapper.unmount()
  })
})
