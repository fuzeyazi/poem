import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { matchAllusions, type VerseToken } from '@/utils/allusionMatcher'
import { ALLUSION_SEEDS, type Allusion } from '@/utils/allusionSeed'
import AllusionCard from '@/components/allusion/AllusionCard.vue'

describe('诗词典故知识库种子数据 (allusionSeed)', () => {
  it('内置 20 个高品质古典文化典故种子', () => {
    expect(ALLUSION_SEEDS).toHaveLength(20)
  })

  it('涵盖 Phase 1 需求指定的 20 大核心文化意象', () => {
    const requiredNames = [
      '折柳', '豆蔻', '尺素', '登高', '沧海', '梦蝶', '沉鱼', '黍离', '采薇', '青鸟',
      '杜宇', '投笔', '阳关', '鹿鸣', '塞翁失马', '烂柯', '望帝', '题红', '秉烛', '乘槎'
    ]
    const seedNames = ALLUSION_SEEDS.map(a => a.name)
    for (const name of requiredNames) {
      expect(seedNames).toContain(name)
    }
  })

  it('每条种子数据包含完整文化溯源字段（出处、文言原文、源流背景、延伸名句）', () => {
    for (const item of ALLUSION_SEEDS) {
      expect(item.id).toBeGreaterThan(0)
      expect(item.name).toBeTruthy()
      expect(item.pinyin).toBeTruthy()
      expect(item.dynasty).toBeTruthy()
      expect(item.origin).toBeTruthy()
      expect(item.originQuote).toBeTruthy()
      expect(item.story).toBeTruthy()
      expect(item.relatedQuotes).toBeTruthy()
      expect(item.sentiment).toBeTruthy()
    }
  })
})

describe('典故无损分词与识别引擎 (allusionMatcher)', () => {
  it('处理空字符串与 null/undefined 边界', () => {
    expect(matchAllusions('')).toEqual([])
    // @ts-expect-error 测试防御性
    expect(matchAllusions(null)).toEqual([])
    // @ts-expect-error 测试防御性
    expect(matchAllusions(undefined)).toEqual([])
  })

  it('无典故文本原样返回单个 text Token', () => {
    const text = '床前明月光，疑是地上霜。'
    const tokens = matchAllusions(text)
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toEqual({
      type: 'text',
      content: text
    })
  })

  it('精准识别单条典故并保持标点与上下文位置严格一致', () => {
    const text = '此夜曲中闻折柳，何人不起故园情。'
    const tokens = matchAllusions(text)
    expect(tokens).toHaveLength(3)

    expect(tokens[0]).toEqual({
      type: 'text',
      content: '此夜曲中闻'
    })
    expect(tokens[1].type).toBe('allusion')
    expect(tokens[1].content).toBe('折柳')
    expect(tokens[1].allusion?.name).toBe('折柳')
    expect(tokens[1].allusion?.dynasty).toBe('汉代')
    expect(tokens[2]).toEqual({
      type: 'text',
      content: '，何人不起故园情。'
    })

    // 拼接还原必须与原文本 100% 一致
    const reconstructed = tokens.map(t => t.content).join('')
    expect(reconstructed).toBe(text)
  })

  it('精准识别一行中的多个典故', () => {
    // 假设一行中同时包含两个典故：沧海 与 梦蝶
    const text = '沧海月明心如梦蝶，何处寄相思。'
    const tokens = matchAllusions(text)

    const allusionTokens = tokens.filter(t => t.type === 'allusion')
    expect(allusionTokens).toHaveLength(2)
    expect(allusionTokens[0].content).toBe('沧海')
    expect(allusionTokens[1].content).toBe('梦蝶')

    // 严格保留中间与后文的字符
    expect(tokens.map(t => t.content).join('')).toBe(text)
  })

  it('支持 4 字成语长典故优先匹配（贪心最长匹配）', () => {
    const text = '世事无常如塞翁失马，何须介怀。'
    const tokens = matchAllusions(text)
    const allusionToken = tokens.find(t => t.type === 'allusion')
    expect(allusionToken).toBeDefined()
    expect(allusionToken?.content).toBe('塞翁失马')
    expect(allusionToken?.allusion?.name).toBe('塞翁失马')
    expect(tokens.map(t => t.content).join('')).toBe(text)
  })

  it('支持自定义词典并覆盖默认种子', () => {
    const customDict: Allusion[] = [
      {
        id: 101,
        name: '明月',
        origin: '《古诗十九首》',
        story: '古人借明月抒发思乡与怀人情怀。'
      }
    ]
    const text = '床前明月光，疑是地上霜。'
    const tokens = matchAllusions(text, customDict)
    expect(tokens).toHaveLength(3)
    expect(tokens[0].content).toBe('床前')
    expect(tokens[1].content).toBe('明月')
    expect(tokens[1].type).toBe('allusion')
    expect(tokens[1].allusion?.id).toBe(101)
    expect(tokens[2].content).toBe('光，疑是地上霜。')
  })
})

describe('典故溯源微卡片组件 (AllusionCard)', () => {
  const mockAllusion: Allusion = {
    id: 1,
    name: '折柳',
    pinyin: 'zhé liǔ',
    dynasty: '汉代',
    origin: '《三辅黄图·卷六·桥》',
    originQuote: '霸桥在长安东，跨水作桥。汉人送客至此桥，折柳赠别。',
    story: '古代长安霸桥两岸植柳。因柳与留谐音，古人送别时折柳相赠，表达依依惜别、挽留之意。',
    relatedQuotes: '李白《春夜洛城闻笛》：“此夜曲中闻折柳，何人不起故园情。”\n柳永《雨霖铃》：“今宵酒醒何处？杨柳岸，晓风残月。”',
    sentiment: '惜别怀远'
  }

  it('完整渲染微卡片的核心信息区块', () => {
    const wrapper = mount(AllusionCard, {
      props: {
        allusion: mockAllusion
      }
    })

    // 标题与拼音
    expect(wrapper.find('.allusion-title').text()).toBe('折柳')
    expect(wrapper.find('.allusion-pinyin').text()).toBe('zhé liǔ')

    // 朝代与意象标签
    expect(wrapper.find('.dynasty-tag').text()).toBe('汉代')
    expect(wrapper.find('.sentiment-tag').text()).toBe('惜别怀远')

    // 朱砂小印
    expect(wrapper.find('.seal-mark').text()).toBe('典')

    // 出处与原文引用
    expect(wrapper.find('.origin-source').text()).toBe('《三辅黄图·卷六·桥》')
    expect(wrapper.find('.origin-quote').text()).toContain('霸桥在长安东')

    // 源流背景故事
    expect(wrapper.find('.story-text').text()).toContain('古代长安霸桥两岸植柳')

    // 延伸诗句列表
    const quoteItems = wrapper.findAll('.quote-item')
    expect(quoteItems).toHaveLength(2)
    expect(quoteItems[0].text()).toContain('李白《春夜洛城闻笛》')
    expect(quoteItems[1].text()).toContain('柳永《雨霖铃》')
  })

  it('当缺少可选字段时能够优雅容错渲染', () => {
    const sparseAllusion: Allusion = {
      id: 99,
      name: '简易典故',
      origin: '古代文献',
      story: '简要说明背景。'
    }

    const wrapper = mount(AllusionCard, {
      props: {
        allusion: sparseAllusion
      }
    })

    expect(wrapper.find('.allusion-title').text()).toBe('简易典故')
    expect(wrapper.find('.allusion-pinyin').exists()).toBe(false)
    expect(wrapper.find('.dynasty-tag').exists()).toBe(false)
    expect(wrapper.find('.origin-quote').exists()).toBe(false)
    expect(wrapper.find('.quotes-section').exists()).toBe(false)
    expect(wrapper.find('.story-text').text()).toBe('简要说明背景。')
  })
})
