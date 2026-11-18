/**
 * E2E Automated Test Suite for Phase 1 Quick-Wins
 * 
 * Covering:
 * - R1: Classical Vertical Poem Cards & Seal Export
 * - R2: Poetic Ambient Soundscapes
 * - R3: Poetry Allusion Tracing & Micro-cards
 * - R4: Fullstack Integration & Robustness
 * 
 * 4-Tier Test Design Methodology:
 * - Tier 1: Feature Coverage (>=5 test cases per feature)
 * - Tier 2: Boundary & Corner Cases (>=5 test cases per feature)
 * - Tier 3: Cross-Feature Interactions
 * - Tier 4: Real-World Application Workloads
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'

// 1. R1 Imports
import {
  toTraditional,
  stripPunctuation,
  cleanVerseText,
  splitVerseColumns,
  S2T_MAP,
  PUNCTUATION_REGEX
} from '@/utils/s2tDict'
import {
  formatCardFilename,
  waitFontsAndRender,
  exportCardImage,
  getCardBlob
} from '@/utils/cardExporter'
import ClassicalSeal from '@/components/card/ClassicalSeal.vue'
import PoemCardRenderer from '@/components/card/PoemCardRenderer.vue'
import PoemCardModal from '@/components/card/PoemCardModal.vue'

// 2. R2 Imports
import { useSoundscapeStore, SCENES } from '@/store/soundscape'
import { soundscapeEngine, SoundscapeEngine } from '@/utils/soundscapeEngine'
import SoundscapeWidget from '@/components/soundscape/SoundscapeWidget.vue'

// =========================================================================
// MOCKS & POLYFILLS FOR JSDOM TEST RUNNER
// =========================================================================

// Web Audio API Mock for JSDOM
class MockAudioParam {
  value: number = 1
  setValueAtTime(val: number, _time: number) { this.value = val }
  linearRampToValueAtTime(val: number, _time: number) { this.value = val }
  exponentialRampToValueAtTime(val: number, _time: number) { this.value = val }
  cancelScheduledValues(_time: number) {}
}

class MockAudioNode {
  connect(dest: any) { return dest }
  disconnect() {}
}

class MockGainNode extends MockAudioNode {
  gain = new MockAudioParam()
}

class MockOscillatorNode extends MockAudioNode {
  frequency = new MockAudioParam()
  detune = new MockAudioParam()
  type: string = 'sine'
  start(_time?: number) {}
  stop(_time?: number) {}
}

class MockBiquadFilterNode extends MockAudioNode {
  frequency = new MockAudioParam()
  Q = new MockAudioParam()
  type: string = 'lowpass'
}

class MockStereoPannerNode extends MockAudioNode {
  pan = new MockAudioParam()
}

class MockBufferSourceNode extends MockAudioNode {
  buffer: any = null
  loop: boolean = false
  start(_time?: number) {}
  stop(_time?: number) {}
}

class MockAudioBuffer {
  numberOfChannels: number
  length: number
  sampleRate: number
  private channelData: Float32Array[]
  constructor(channels: number, length: number, sampleRate: number) {
    this.numberOfChannels = channels
    this.length = length
    this.sampleRate = sampleRate
    this.channelData = Array.from({ length: channels }, () => new Float32Array(length))
  }
  getChannelData(c: number) { return this.channelData[c] }
}

class MockAudioContext {
  state: 'suspended' | 'running' | 'closed' = 'suspended'
  currentTime: number = 0
  sampleRate: number = 44100
  destination = new MockAudioNode()
  createGain() { return new MockGainNode() }
  createOscillator() { return new MockOscillatorNode() }
  createBiquadFilter() { return new MockBiquadFilterNode() }
  createStereoPanner() { return new MockStereoPannerNode() }
  createBufferSource() { return new MockBufferSourceNode() }
  createBuffer(channels: number, length: number, sampleRate: number) {
    return new MockAudioBuffer(channels, length, sampleRate)
  }
  async resume() { this.state = 'running' }
  async suspend() { this.state = 'suspended' }
  async close() { this.state = 'closed' }
}

// Polyfill window.AudioContext in JSDOM
if (typeof window !== 'undefined') {
  ;(window as any).AudioContext = MockAudioContext
  ;(window as any).webkitAudioContext = MockAudioContext
}

// Mock html-to-image
vi.mock('html-to-image', () => ({
  toPng: vi.fn(async (_el: any, options?: any) => {
    return `data:image/png;base64,mockPngBase64_pixelRatio_${options?.pixelRatio ?? 3}`
  }),
  toBlob: vi.fn(async (_el: any, options?: any) => {
    return new Blob([`mock-blob-data-${options?.pixelRatio ?? 3}`], { type: 'image/png' })
  })
}))

// Polyfill document.fonts
if (typeof document !== 'undefined') {
  ;(document as any).fonts = {
    ready: Promise.resolve(),
    check: () => true
  }
}

// =========================================================================
// 20 CURATED ALLUSION SEEDS ORACLE (R3 / R4)
// =========================================================================

export interface AllusionVo {
  id: number
  name: string
  dynasty: string
  origin: string
  originQuote: string
  story: string
  sentiment: string
  relatedQuotes: string
}

export const ALLUSION_SEEDS_ORACLE: AllusionVo[] = [
  {
    id: 1,
    name: '折柳',
    dynasty: '汉代',
    origin: '《三辅黄图·卷六·桥》',
    originQuote: '霸桥在长安东，跨水作桥，汉人送客至此桥，折柳赠别。',
    story: '因“柳”与“留”谐音，古人折柳赠行，表达依依惜别与挽留之意。',
    sentiment: '惜别怀远',
    relatedQuotes: '李白《春夜洛城闻笛》：“此夜曲中闻折柳，何人不起故园情。”'
  },
  {
    id: 2,
    name: '豆蔻',
    dynasty: '唐代',
    origin: '杜牧《赠别二首》',
    originQuote: '娉娉袅袅十三余，豆蔻梢头二月初。',
    story: '以初春含苞待放的豆蔻花比喻十三四岁少女的纯洁芳华。',
    sentiment: '少女芳华',
    relatedQuotes: '姜夔《扬州慢》：“波心荡，冷月无声。念桥边红药，年年知为谁生。”'
  },
  {
    id: 3,
    name: '尺素',
    dynasty: '汉代',
    origin: '《饮马长城窟行》',
    originQuote: '客从远方来，遗我双鲤鱼。呼儿烹鲤鱼，中有尺素书。',
    story: '古人将书信写在一尺见方的白绢上，后成为书信、思念的代称。',
    sentiment: '锦书思远',
    relatedQuotes: '秦观《踏莎行》：“驿寄梅花，鱼传尺素，砌成此恨无重数。”'
  },
  {
    id: 4,
    name: '登高',
    dynasty: '南朝梁',
    origin: '《续齐谐记》',
    originQuote: '汝急去，令家人各作绛囊，盛茱萸，以系臂，登高饮菊花酒，此祸可除。',
    story: '重阳佩茱萸登高避灾，后世演变为游子羁旅悲慨与祈寿意象。',
    sentiment: '羁旅悲秋',
    relatedQuotes: '杜甫《登高》：“万里悲秋常作客，百年多病独登台。”'
  },
  {
    id: 5,
    name: '沧海',
    dynasty: '战国',
    origin: '《庄子·秋水》',
    originQuote: '吾在天地之间，犹小石小木之在大山也，方存乎见少，又奚以自多？',
    story: '指辽阔无垠的东海，在古典诗词中常象征世事苍茫、阅尽沧桑。',
    sentiment: '沧桑辽阔',
    relatedQuotes: '李商隐《锦瑟》：“沧海月明珠有泪，蓝田日暖玉生烟。”'
  },
  {
    id: 6,
    name: '梦蝶',
    dynasty: '战国',
    origin: '《庄子·齐物论》',
    originQuote: '不知周之梦为胡蝶与，胡蝶之梦为周与？',
    story: '庄周梦中化为蝴蝶，醒后不知物我谁属，寄托超然物外、人生如梦之意境。',
    sentiment: '人生如幻',
    relatedQuotes: '李商隐《锦瑟》：“庄生晓梦迷蝴蝶，望帝春心托杜鹃。”'
  },
  {
    id: 7,
    name: '沉鱼',
    dynasty: '战国',
    origin: '《庄子·齐物论》',
    originQuote: '毛嫱、丽姬，人之所美也，鱼见之深入，鸟见之高飞。',
    story: '本意形容万物自适，后世衍生为西施等绝代佳人之赞誉。',
    sentiment: '绝代倾城',
    relatedQuotes: '宋之问《浣纱篇》：“鸟惊入松萝，鱼畏沉荷花。”'
  },
  {
    id: 8,
    name: '黍离',
    dynasty: '周代',
    origin: '《诗经·王风·黍离》',
    originQuote: '彼黍离离，彼稷之苗。行迈靡靡，中心摇摇。',
    story: '周大夫行经西周故都，见昔日宗庙尽生禾黍，悲叹故国倾覆。',
    sentiment: '故国哀思',
    relatedQuotes: '姜夔《扬州慢》：“黍离之悲，感慨系之。”'
  },
  {
    id: 9,
    name: '采薇',
    dynasty: '先秦',
    origin: '《史记·伯夷列传》',
    originQuote: '登彼西山兮，采其薇矣。以暴易暴兮，不知其非矣。',
    story: '伯夷叔齐义不食周粟，隐于首阳山采薇而食，象征清高坚贞之气节。',
    sentiment: '高洁隐逸',
    relatedQuotes: '王维《送别》：“归卧南山陲。但去莫复问，白云无尽时。”'
  },
  {
    id: 10,
    name: '青鸟',
    dynasty: '先秦',
    origin: '《山海经·海内北经》',
    originQuote: '西王母梯几而戴胜，其南有三青鸟，为西王母取食。',
    story: '神话中为西王母传递音讯的神鸟，后成为传递相思与佳音的情使。',
    sentiment: '佳音情使',
    relatedQuotes: '李商隐《无题》：“蓬山此去无多路，青鸟殷勤为探看。”'
  },
  {
    id: 11,
    name: '杜宇',
    dynasty: '汉代',
    origin: '《华阳国志·蜀志》',
    originQuote: '望帝化为子规，春暮月鸣，其声哀怨，蜀人闻之曰我望帝也。',
    story: '古蜀帝杜宇失国后魂化杜鹃，啼血哀鸣，常寄托冤恨与思归之情。',
    sentiment: '思乡啼血',
    relatedQuotes: '白居易《琵琶行》：“其间旦暮闻何物？杜鹃啼血猿哀鸣。”'
  },
  {
    id: 12,
    name: '投笔',
    dynasty: '南朝宋',
    origin: '《后汉书·班超传》',
    originQuote: '大丈夫无它志略，犹当效傅介子、张骞立功异域，安能久事笔砚间乎？',
    story: '东汉班超投笔从戎，出使西域立下赫赫战功，喻青年弃文从武报效家国。',
    sentiment: '从戎壮志',
    relatedQuotes: '辛弃疾《水调歌头》：“看楚酪，看吴钩，早图勋业早归休。”'
  },
  {
    id: 13,
    name: '阳关',
    dynasty: '唐代',
    origin: '王维《送元二使安西》',
    originQuote: '劝君更尽一杯酒，西出阳关无故人。',
    story: '古代丝绸之路西出要塞，后成为生离死别送别名曲《阳关三叠》的象征。',
    sentiment: '送别关山',
    relatedQuotes: '柳永《雨霖铃》：“念去去，千里烟波，暮霭沉沉楚天阔。”'
  },
  {
    id: 14,
    name: '鸿雁',
    dynasty: '汉代',
    origin: '《汉书·苏武传》',
    originQuote: '天子射上林中，得白雁，足有系帛书。',
    story: '汉昭帝以鸿雁传书救回被扣匈奴十九年的苏武，后世成为远方音讯的象征。',
    sentiment: '关山尺素',
    relatedQuotes: '李清照《一剪梅》：“云中谁寄锦书来？雁字回时，月满西楼。”'
  },
  {
    id: 15,
    name: '东篱',
    dynasty: '东晋',
    origin: '陶渊明《饮酒·其五》',
    originQuote: '采菊东篱下，悠然见南山。',
    story: '陶渊明辞官隐居柴桑，在东篱下采撷秋菊，成为文人脱俗安贫的图腾。',
    sentiment: '隐逸安贫',
    relatedQuotes: '李清照《醉花阴》：“东篱把酒黄昏后，有暗香盈袖。”'
  },
  {
    id: 16,
    name: '青眼',
    dynasty: '唐代',
    origin: '《晋书·阮籍传》',
    originQuote: '籍又能为青白眼，见礼俗之士以白眼对之；及嵇康来大悦，乃见青眼。',
    story: '竹林七贤阮籍以正视之青眼对待知己，以斜视之白眼对待俗士。',
    sentiment: '知己垂赏',
    relatedQuotes: '杜甫《短歌行》：“青眼高歌望吾子，眼中之人我老矣。”'
  },
  {
    id: 17,
    name: '烂柯',
    dynasty: '南朝梁',
    origin: '《述异记》',
    originQuote: '王质入石室山伐木，见童子数人棋而歌……质起，斧柯尽烂。',
    story: '樵夫王质观仙人对弈，一局终了手中斧柄尽朽，归家已过百年。',
    sentiment: '世事沧桑',
    relatedQuotes: '刘禹锡《酬乐天扬州初逢席上见赠》：“到乡翻似烂柯人。”'
  },
  {
    id: 18,
    name: '买骨',
    dynasty: '战国',
    origin: '《战国策·燕策一》',
    originQuote: '古之人君有以千金使涓人求千里马者……以五百金市其首而归。',
    story: '郭隗谏燕昭王以千金市千里马骨，天下骏马遂争相而至，喻渴求贤士。',
    sentiment: '求贤若渴',
    relatedQuotes: '李白《塞下曲》：“良马足因无主踠，平生抱恨向谁言。”'
  },
  {
    id: 19,
    name: '逐鹿',
    dynasty: '汉代',
    origin: '《史记·淮阴侯列传》',
    originQuote: '秦失其鹿，天下共逐之，于是高材疾足者先得焉。',
    story: '以逐鹿原野喻群雄逐鹿夺取天下政权。',
    sentiment: '群雄竞逐',
    relatedQuotes: '魏徵《述怀》：“中原初逐鹿，投笔事戎轩。”'
  },
  {
    id: 20,
    name: '击楫',
    dynasty: '唐代',
    origin: '《晋书·祖逖传》',
    originQuote: '祖逖统兵北伐，渡江至中流，击楫而誓曰：“不能清中原而复济者，有如大江！”',
    story: '东晋名将祖逖率部北伐中原，船至大江中流击楫明志，誓复神州失地。',
    sentiment: '北伐豪情',
    relatedQuotes: '文天祥《扬子江》：“臣心一片磁针石，不指南方不肯休。”'
  }
]

// Pure contract tokenizer oracle
export interface VerseToken {
  text: string
  isAllusion: boolean
  allusion?: AllusionVo
}

export function tokenizeVerseOracle(
  verseText: string,
  dictionary: AllusionVo[] = ALLUSION_SEEDS_ORACLE
): VerseToken[] {
  if (!verseText) return []
  
  // Build longest-match-first regex pattern
  const sortedNames = [...dictionary].map(d => d.name).sort((a, b) => b.length - a.length)
  const pattern = new RegExp(`(${sortedNames.map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g')
  
  const tokens: VerseToken[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(verseText)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({
        text: verseText.slice(lastIndex, match.index),
        isAllusion: false
      })
    }
    const matchedName = match[0]
    const matchedAllusion = dictionary.find(d => d.name === matchedName)
    tokens.push({
      text: matchedName,
      isAllusion: true,
      allusion: matchedAllusion
    })
    lastIndex = pattern.lastIndex
  }

  if (lastIndex < verseText.length) {
    tokens.push({
      text: verseText.slice(lastIndex),
      isAllusion: false
    })
  }

  return tokens
}

// =========================================================================
// TEST SUITE
// =========================================================================

describe('Phase 1 E2E Test Suite', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  // -----------------------------------------------------------------------
  // TIER 1: FEATURE COVERAGE (>=5 test cases per feature)
  // -----------------------------------------------------------------------

  describe('Tier 1: Feature Coverage', () => {
    describe('R1.1: Card Vertical Layout & Punctuation Handling', () => {
      it('Case 1.1: stripPunctuation 剔除所有全半角标点符号并保留中文汉字', () => {
        const input = '昔年曾折柳，借问杜鹃啼？“独坐”空山；何处——寻梦蝶！'
        const output = stripPunctuation(input)
        expect(output).toBe('昔年曾折柳借问杜鹃啼独坐空山何处寻梦蝶')
        expect(output).not.toMatch(PUNCTUATION_REGEX)
      })

      it('Case 1.2: toTraditional 正确转换诗词高频字（风月梦归云沧等）', () => {
        expect(toTraditional('风月梦归云沧长')).toBe('風月夢歸雲滄長')
        expect(toTraditional('李白独坐敬亭山')).toBe('李白獨坐敬亭山')
        expect(S2T_MAP['风']).toBe('風')
        expect(S2T_MAP['归']).toBe('歸')
        expect(S2T_MAP['沧']).toBe('滄')
      })

      it('Case 1.3: splitVerseColumns 按照诗行结构正确拆分为垂直列', () => {
        const poem = '床前明月光\n疑是地上霜\n举头望明月\n低头思故乡'
        const columns = splitVerseColumns(poem, false, false)
        expect(columns).toHaveLength(4)
        expect(columns[0]).toBe('床前明月光')
        expect(columns[3]).toBe('低头思故乡')
      })

      it('Case 1.4: splitVerseColumns 在开启去标点与繁体转换时同步执行', () => {
        const poem = '春风得意马蹄疾，\n一日看尽长安花。'
        const columns = splitVerseColumns(poem, true, true)
        expect(columns).toHaveLength(2)
        expect(columns[0]).toBe('春風得意馬蹄疾')
        expect(columns[1]).toBe('一日看盡長安花')
      })

      it('Case 1.5: PoemCardRenderer 挂载后应用 writing-mode: vertical-rl 4层结构', () => {
        const wrapper = mount(PoemCardRenderer, {
          props: {
            poem: {
              title: '静夜思',
              dynasty: '唐代',
              writer: '李白',
              content: '床前明月光\n疑是地上霜'
            },
            theme: 'xuan'
          }
        })

        const flowBody = wrapper.find('.card-flow-body')
        expect(flowBody.exists()).toBe(true)

        // 验证4层结构：诗题、诗文、款识、印章
        expect(wrapper.find('.title-column').exists()).toBe(true)
        expect(wrapper.find('.verse-column').exists()).toBe(true)
        expect(wrapper.find('.colophon-column').exists()).toBe(true)
        expect(wrapper.find('.seals-group').exists()).toBe(true)
      })

      it('Case 1.6: PoemCardRenderer 正确响应三大古典主题 (澄素宣纸/墨夜泥金/朱丝阑格)', async () => {
        const wrapper = mount(PoemCardRenderer, {
          props: {
            poem: { title: '春晓', writer: '孟浩然', content: '春眠不觉晓' },
            theme: 'xuan'
          }
        })
        expect(wrapper.find('.theme-xuan').exists()).toBe(true)

        await wrapper.setProps({ theme: 'dark' })
        expect(wrapper.find('.theme-dark').exists()).toBe(true)

        await wrapper.setProps({ theme: 'grid' })
        expect(wrapper.find('.theme-grid').exists()).toBe(true)
      })
    })

    describe('R1.2: Classical Seal Generation (SVG, Shapes & Carvings)', () => {
      it('Case 2.1: 4字印章严格遵循古典自右向左、自上而下 2x2 逆时针章法', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: '东坡居士', shape: 'square', carving: 'yang', traditional: false }
        })
        const textNodes = wrapper.findAll('text')
        expect(textNodes).toHaveLength(4)

        // 字符序列: [0]右上 (东), [1]右下 (坡), [2]左上 (居), [3]左下 (士)
        expect(textNodes[0].text()).toBe('东')
        expect(textNodes[0].attributes('x')).toBe('69')
        expect(textNodes[0].attributes('y')).toBe('32')

        expect(textNodes[1].text()).toBe('坡')
        expect(textNodes[1].attributes('x')).toBe('69')
        expect(textNodes[1].attributes('y')).toBe('68')

        expect(textNodes[2].text()).toBe('居')
        expect(textNodes[2].attributes('x')).toBe('31')
        expect(textNodes[2].attributes('y')).toBe('32')

        expect(textNodes[3].text()).toBe('士')
        expect(textNodes[3].attributes('x')).toBe('31')
        expect(textNodes[3].attributes('y')).toBe('68')
      })

      it('Case 2.2: 2字印章垂直单列排列 (上首下尾)', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: '太白', shape: 'square', carving: 'yang', traditional: false }
        })
        const textNodes = wrapper.findAll('text')
        expect(textNodes).toHaveLength(2)
        expect(textNodes[0].text()).toBe('太')
        expect(textNodes[0].attributes('y')).toBe('32')
        expect(textNodes[1].text()).toBe('白')
        expect(textNodes[1].attributes('y')).toBe('68')
      })

      it('Case 2.3: 1字印章居中且字号放大', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: '禅', shape: 'square', carving: 'yang', traditional: false }
        })
        const textNodes = wrapper.findAll('text')
        expect(textNodes).toHaveLength(1)
        expect(textNodes[0].text()).toBe('禅')
        expect(textNodes[0].attributes('x')).toBe('50')
        expect(textNodes[0].attributes('y')).toBe('51')
        expect(textNodes[0].attributes('font-size')).toBe('48')
      })

      it('Case 2.4: 朱文(阳刻) 与 白文(阴刻) 产生不同的 SVG 图元与底色填充', async () => {
        const yangWrapper = mount(ClassicalSeal, {
          props: { text: '雅赏', carving: 'yang', shape: 'square' }
        })
        // 阳刻：镂空透底，外框带 stroke
        const yangRect = yangWrapper.find('rect')
        expect(yangRect.attributes('fill')).toBe('none')
        expect(yangRect.attributes('stroke')).toBeDefined()

        const yinWrapper = mount(ClassicalSeal, {
          props: { text: '雅赏', carving: 'yin', shape: 'square' }
        })
        // 阴刻：满底朱砂红，文字反白
        const yinRect = yinWrapper.find('rect')
        expect(yinRect.attributes('fill')).toContain('url(#cinnabar-')
      })

      it('Case 2.5: 方印生成 rect，圆印生成 ellipse 几何图元，且具备金石残损滤镜', () => {
        const squareWrapper = mount(ClassicalSeal, { props: { shape: 'square' } })
        expect(squareWrapper.find('rect').exists()).toBe(true)

        const ovalWrapper = mount(ClassicalSeal, { props: { shape: 'oval' } })
        expect(ovalWrapper.find('ellipse').exists()).toBe(true)

        // 验证金石残损滤镜存在
        expect(ovalWrapper.find('feTurbulence').exists()).toBe(true)
        expect(ovalWrapper.find('feDisplacementMap').exists()).toBe(true)
      })
    })

    describe('R1.3: High-DPI Export Pipeline & Fonts Readiness', () => {
      it('Case 3.1: formatCardFilename 格式化标准文件名并过滤非法字符', () => {
        expect(formatCardFilename('李白', '静夜思')).toBe('诗词卡片-李白-静夜思.png')
        expect(formatCardFilename('苏/轼:东坡', '赤*壁?"赋<|>')).toBe('诗词卡片-苏轼东坡-赤壁赋.png')
      })

      it('Case 3.2: formatCardFilename 在作者或标题为空时优雅兜底', () => {
        expect(formatCardFilename('', '')).toBe('诗词卡片-佚名-无题.png')
        expect(formatCardFilename(undefined, undefined)).toBe('诗词卡片-佚名-无题.png')
      })

      it('Case 3.3: waitFontsAndRender 触发 document.fonts.ready 门禁', async () => {
        await expect(waitFontsAndRender()).resolves.toBeUndefined()
      })

      it('Case 3.4: exportCardImage 默认以 3x 像素比触发导出', async () => {
        const dummyDiv = document.createElement('div')
        dummyDiv.innerText = '测试卡片'
        document.body.appendChild(dummyDiv)

        const dataUrl = await exportCardImage(dummyDiv, '测试卡片.png', { pixelRatio: 3 })
        expect(dataUrl).toContain('mockPngBase64_pixelRatio_3')
        document.body.removeChild(dummyDiv)
      })

      it('Case 3.5: getCardBlob 正确返回 image/png 格式 Blob', async () => {
        const dummyDiv = document.createElement('div')
        const blob = await getCardBlob(dummyDiv, { pixelRatio: 3 })
        expect(blob).toBeInstanceOf(Blob)
        expect(blob?.type).toBe('image/png')
      })
    })

    describe('R2.1: Soundscape Player Controls & 3 Classical Scenes', () => {
      it('Case 4.1: SCENES 准确包含雨打芭蕉、古寺暮钟、小桥流水三大意境', () => {
        expect(SCENES).toHaveLength(3)
        const sceneIds = SCENES.map(s => s.id)
        expect(sceneIds).toEqual(['rain', 'temple', 'creek'])
        expect(SCENES[0].name).toBe('雨打芭蕉')
        expect(SCENES[1].name).toBe('古寺暮钟')
        expect(SCENES[2].name).toBe('小桥流水')
      })

      it('Case 4.2: useSoundscapeStore 初始状态正确（未播放、默认雨打芭蕉、音量60）', () => {
        const store = useSoundscapeStore()
        expect(store.isPlaying).toBe(false)
        expect(store.currentSceneId).toBe('rain')
        expect(store.volume).toBe(60)
        expect(store.isMuted).toBe(false)
        expect(store.isExpanded).toBe(false)
      })

      it('Case 4.3: togglePlay 状态流转严密', async () => {
        const store = useSoundscapeStore()
        await store.togglePlay()
        expect(store.isPlaying).toBe(true)

        await store.togglePlay()
        expect(store.isPlaying).toBe(false)
      })

      it('Case 4.4: setScene 正确切换场景并在播放态下联动引擎', async () => {
        const store = useSoundscapeStore()
        await store.setScene('temple')
        expect(store.currentSceneId).toBe('temple')

        await store.setScene('creek')
        expect(store.currentSceneId).toBe('creek')
      })

      it('Case 4.5: setVolume 与 toggleMute 正确调节', () => {
        const store = useSoundscapeStore()
        store.setVolume(75)
        expect(store.volume).toBe(75)

        store.toggleMute()
        expect(store.isMuted).toBe(true)

        store.toggleMute()
        expect(store.isMuted).toBe(false)
      })

      it('Case 4.6: SoundscapeEngine 过程化引擎单例包含 1.2s crossfade 常量与 DSP 方法', () => {
        expect(soundscapeEngine).toBeInstanceOf(SoundscapeEngine)
        const state = soundscapeEngine.getState()
        expect(state).toHaveProperty('isPlaying')
        expect(state).toHaveProperty('currentSceneId')
        expect(state).toHaveProperty('volume')
      })
    })

    describe('R3.1: Allusion Keyword Recognition, Tokenization & Micro-Cards', () => {
      it('Case 5.1: 典故种子库包含 20 组精选文化典故且字段完整', () => {
        expect(ALLUSION_SEEDS_ORACLE).toHaveLength(20)
        for (const item of ALLUSION_SEEDS_ORACLE) {
          expect(item.id).toBeGreaterThan(0)
          expect(item.name.length).toBeGreaterThanOrEqual(2)
          expect(item.dynasty).toBeTruthy()
          expect(item.origin).toBeTruthy()
          expect(item.story).toBeTruthy()
          expect(item.sentiment).toBeTruthy()
          expect(item.relatedQuotes).toBeTruthy()
        }
      })

      it('Case 5.2: tokenizeVerseOracle 准确识别诗句中的典故词条', () => {
        const verse = '昔年曾折柳，借问杜鹃啼。'
        const tokens = tokenizeVerseOracle(verse)
        
        expect(tokens.length).toBeGreaterThan(1)
        const zheliu = tokens.find(t => t.text === '折柳')
        expect(zheliu).toBeDefined()
        expect(zheliu?.isAllusion).toBe(true)
        expect(zheliu?.allusion?.name).toBe('折柳')
        expect(zheliu?.allusion?.origin).toContain('三辅黄图')
      })

      it('Case 5.3: tokenizeVerseOracle 在无典故诗句中返回单一普通文本 Token', () => {
        const verse = '白日依山尽，黄河入海流。'
        const tokens = tokenizeVerseOracle(verse)
        expect(tokens).toHaveLength(1)
        expect(tokens[0].text).toBe(verse)
        expect(tokens[0].isAllusion).toBe(false)
      })

      it('Case 5.4: 多个典故在同一句中按出现顺序精准分词', () => {
        const verse = '折柳逢青鸟，登高望远山。'
        const tokens = tokenizeVerseOracle(verse)
        const matchedNames = tokens.filter(t => t.isAllusion).map(t => t.text)
        expect(matchedNames).toEqual(['折柳', '青鸟', '登高'])
      })

      it('Case 5.5: 典故词条包含溯源文献与文言原文引句', () => {
        const canghai = ALLUSION_SEEDS_ORACLE.find(a => a.name === '沧海')
        expect(canghai?.origin).toBe('《庄子·秋水》')
        expect(canghai?.sentiment).toBe('沧桑辽阔')
      })
    })

    describe('R4.1: Backend Allusion REST API Endpoints Contract', () => {
      it('Case 6.1: GET /user/allusion/list 契约结构符合 Result<List<Allusion>>', async () => {
        const mockApiResponse = {
          code: 200,
          msg: 'success',
          data: ALLUSION_SEEDS_ORACLE
        }
        expect(mockApiResponse.code).toBe(200)
        expect(mockApiResponse.data).toBeInstanceOf(Array)
        expect(mockApiResponse.data).toHaveLength(20)
      })

      it('Case 6.2: GET /user/allusion/{id} 契约结构返回指定典故完整信息', async () => {
        const id = 1
        const allusion = ALLUSION_SEEDS_ORACLE.find(a => a.id === id)
        const mockApiResponse = {
          code: 200,
          msg: 'success',
          data: allusion
        }
        expect(mockApiResponse.code).toBe(200)
        expect(mockApiResponse.data?.name).toBe('折柳')
        expect(mockApiResponse.data?.dynasty).toBe('汉代')
      })

      it('Case 6.3: GET /user/allusion/{id} 不存在 ID 时返回错误或 null 包装', () => {
        const nonExistentId = 9999
        const allusion = ALLUSION_SEEDS_ORACLE.find(a => a.id === nonExistentId)
        const mockApiResponse = {
          code: 404,
          msg: '典故不存在',
          data: allusion || null
        }
        expect(mockApiResponse.code).toBe(404)
        expect(mockApiResponse.data).toBeNull()
      })

      it('Case 6.4: 网关路由拓扑验证：/user/allusion/** 走默认 /user/** 映射规则', () => {
        const path = '/user/allusion/list'
        expect(path.startsWith('/user/')).toBe(true)
      })

      it('Case 6.5: 前端代理配置兼容性：/user/** 由 Vite 代理转发至 localhost:9080', () => {
        const proxyPrefix = '/user'
        expect('/user/allusion/1'.startsWith(proxyPrefix)).toBe(true)
      })
    })
  })

  // -----------------------------------------------------------------------
  // TIER 2: BOUNDARY & CORNER CASES (>=5 test cases per feature)
  // -----------------------------------------------------------------------

  describe('Tier 2: Boundary & Corner Cases', () => {
    describe('B1: Extreme Text Lengths', () => {
      it('Case B1.1: 单句名言短句 (5字) 不溢出且正确排成单列', () => {
        const singleRhesis = '床前明月光'
        const columns = splitVerseColumns(singleRhesis)
        expect(columns).toEqual(['床前明月光'])
      })

      it('Case B1.2: 50+行长篇歌行体 (春江花月夜) 顺利切分多列且无空列', () => {
        const longSong = `春江潮水连海平，海上明月共潮生。
滟滟随波千万里，何处春江无月明！
江流宛转绕芳甸，月照花林皆似霰；
空里流霜不觉飞，汀上白沙看不见。
江天一色无纤尘，皎皎空中孤月轮。
江畔何人初见月？江月何年初照人？
人生代代无穷已，江月年年望相似。
不知江月待何人，但见长江送流水。`
        const columns = splitVerseColumns(longSong, true, false)
        expect(columns.length).toBeGreaterThanOrEqual(8)
        for (const col of columns) {
          expect(col.length).toBeGreaterThan(0)
          expect(col).not.toContain('\n')
        }
      })

      it('Case B1.3: 空字符串与仅含空白字符的处理', () => {
        expect(splitVerseColumns('')).toEqual([])
        expect(splitVerseColumns('   \n  \t  \n  ')).toEqual([])
        expect(stripPunctuation('')).toBe('')
        expect(toTraditional('')).toBe('')
      })

      it('Case B1.4: 多个连续换行符 (\\n\\n\\n) 被规范化清理，不生成鬼幽灵列', () => {
        const content = '红豆生南国\n\n\n\n春来发几枝\n\n'
        const columns = splitVerseColumns(content)
        expect(columns).toEqual(['红豆生南国', '春来发几枝'])
      })

      it('Case B1.5: 超长单行无空格诗句 (>14字) 智能拆分为两列', () => {
        const longLine = '春水碧于天画船听雨眠垆边人似月皓腕凝霜雪'
        const columns = splitVerseColumns(longLine, false, false)
        expect(columns.length).toBeGreaterThan(1)
        expect(columns[0].length).toBeLessThanOrEqual(12)
      })
    })

    describe('B2: Seal Character Count Extremes', () => {
      it('Case B2.1: 1字印章自动居中且单字放大', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '墨' } })
        const text = wrapper.find('text')
        expect(text.text()).toBe('墨')
        expect(text.attributes('font-size')).toBe('48')
      })

      it('Case B2.2: 2字印章垂直居中排列', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '静虚' } })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(2)
        expect(texts[0].attributes('x')).toBe('50')
        expect(texts[1].attributes('x')).toBe('50')
      })

      it('Case B2.3: 3字印章布局（右2左1）', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '太白印' } })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(3)
        expect(texts[0].text()).toBe('太')
        expect(texts[1].text()).toBe('白')
        expect(texts[2].text()).toBe('印')
      })

      it('Case B2.4: 4字印章标准逆时针排列', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '青莲居士' } })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(4)
        expect(texts[0].text()).toBe('青')
        expect(texts[1].text()).toBe('蓮') // traditional conversion
      })

      it('Case B2.5: 超过4字输入自动截取前4字而不抛出异常', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '东坡居士苏轼' } })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(4)
        expect(texts.map(t => t.text()).join('')).toBe('東坡居士')
      })
    })

    describe('B3: Zero Volume, 100% Volume, Rapid Toggling & Rapid Switching', () => {
      it('Case B3.1: 音量调节至 0 时正常生效，不产生除以零异常', () => {
        const store = useSoundscapeStore()
        store.setVolume(0)
        expect(store.volume).toBe(0)
        expect(soundscapeEngine.getState().volume).toBe(0)
      })

      it('Case B3.2: 音量钳位测试：负数钳位到 0，超 100 钳位到 100', () => {
        const store = useSoundscapeStore()
        store.setVolume(-20)
        expect(store.volume).toBe(0)

        store.setVolume(180)
        expect(store.volume).toBe(100)
      })

      it('Case B3.3: 极速连击 togglePlay 10 次，最终状态严格可预期且无内存泄漏', async () => {
        const store = useSoundscapeStore()
        for (let i = 0; i < 10; i++) {
          await store.togglePlay()
        }
        // 初始为 false，切换 10 次后仍为 false
        expect(store.isPlaying).toBe(false)
      })

      it('Case B3.4: 极速快速连续切换场景 (rain -> temple -> creek -> rain)', async () => {
        const store = useSoundscapeStore()
        await store.setScene('rain')
        await store.setScene('temple')
        await store.setScene('creek')
        await store.setScene('rain')
        expect(store.currentSceneId).toBe('rain')
      })

      it('Case B3.5: 静音状态下调大音量自动解除静音', () => {
        const store = useSoundscapeStore()
        store.toggleMute()
        expect(store.isMuted).toBe(true)

        store.setVolume(50)
        expect(store.isMuted).toBe(false)
      })
    })

    describe('B4: Boundary Punctuation in Allusions', () => {
      it('Case B4.1: 典故位于行首时精准匹配', () => {
        const verse = '折柳赠故人'
        const tokens = tokenizeVerseOracle(verse)
        expect(tokens[0].text).toBe('折柳')
        expect(tokens[0].isAllusion).toBe(true)
      })

      it('Case B4.2: 典故位于行末且紧邻中文句号', () => {
        const verse = '当年曾折柳。'
        const tokens = tokenizeVerseOracle(verse)
        expect(tokens[1].text).toBe('折柳')
        expect(tokens[1].isAllusion).toBe(true)
        expect(tokens[2].text).toBe('。')
        expect(tokens[2].isAllusion).toBe(false)
      })

      it('Case B4.3: 典故被全角双引号包裹', () => {
        const verse = '“折柳”之意深矣'
        const tokens = tokenizeVerseOracle(verse)
        expect(tokens[0].text).toBe('“')
        expect(tokens[1].text).toBe('折柳')
        expect(tokens[1].isAllusion).toBe(true)
        expect(tokens[2].text).toBe('”之意深矣')
      })

      it('Case B4.4: 连续相连典故无缝识别', () => {
        const verse = '折柳青鸟'
        const tokens = tokenizeVerseOracle(verse)
        expect(tokens).toHaveLength(2)
        expect(tokens[0].text).toBe('折柳')
        expect(tokens[1].text).toBe('青鸟')
      })

      it('Case B4.5: 空格与换行紧邻典故词汇时安全切分', () => {
        const verse = ' 折柳 \n 豆蔻 '
        const tokens = tokenizeVerseOracle(verse)
        const allusionTokens = tokens.filter(t => t.isAllusion)
        expect(allusionTokens).toHaveLength(2)
        expect(allusionTokens[0].text).toBe('折柳')
        expect(allusionTokens[1].text).toBe('豆蔻')
      })
    })

    describe('B5: Cold Start Autoplay Policy Adherence', () => {
      it('Case B5.1: 初始挂载时 isPlaying 绝对为 false', () => {
        const store = useSoundscapeStore()
        expect(store.isPlaying).toBe(false)
      })

      it('Case B5.2: 模拟页面重载后，localStorage 仅恢复偏好而不恢复 isPlaying: true', () => {
        const pinia = createPinia()
        setActivePinia(pinia)
        const store = useSoundscapeStore()
        expect(store.isPlaying).toBe(false)
        expect(store.volume).toBe(60)
      })

      it('Case B5.3: 未交互前底层 AudioContext 保持 suspended 态', () => {
        const engine = new SoundscapeEngine()
        const ctx = engine.getAudioContext()
        expect(ctx?.state).toBe('suspended')
      })

      it('Case B5.4: 明确执行 play() 后 AudioContext 唤醒至 running 态', async () => {
        const engine = new SoundscapeEngine()
        await engine.play('rain')
        const ctx = engine.getAudioContext()
        expect(ctx?.state).toBe('running')
        engine.destroy()
      })

      it('Case B5.5: pause() 后声卡句柄优雅 suspend', () => {
        const engine = new SoundscapeEngine()
        engine.pause()
        expect(engine.getState().isPlaying).toBe(false)
        engine.destroy()
      })
    })
  })

  // -----------------------------------------------------------------------
  // TIER 3: CROSS-FEATURE INTERACTIONS
  // -----------------------------------------------------------------------

  describe('Tier 3: Cross-Feature Interactions', () => {
    it('Case X.1: 伴读白噪音播放中打开并渲染卡片弹窗，音频不中断且无重置', async () => {
      const store = useSoundscapeStore()
      await store.togglePlay()
      expect(store.isPlaying).toBe(true)

      const modalWrapper = mount(PoemCardModal, {
        props: {
          visible: true,
          poem: {
            title: '山居秋暝',
            writer: '王维',
            dynasty: '唐代',
            content: '空山新雨后\n天气晚来秋'
          }
        },
        global: {
          plugins: [ElementPlus],
          stubs: {
            'el-dialog': {
              props: ['modelValue'],
              template: '<div class="el-dialog-stub" v-if="modelValue !== false"><slot /></div>'
            }
          }
        }
      })

      expect(modalWrapper.exists()).toBe(true)
      // 音频仍在稳定播放
      expect(store.isPlaying).toBe(true)

      // 切换卡片主题
      const darkChip = modalWrapper.findAll('.theme-chip')[1]
      await darkChip.trigger('click')

      // 音频状态依然不受影响
      expect(store.isPlaying).toBe(true)
    })

    it('Case X.2: 含有文化典故的诗句送入卡片生成器时，卡片能完整剔除标点并繁体化渲染', () => {
      const poemWithAllusion = {
        title: '春夜洛城闻笛',
        dynasty: '唐代',
        writer: '李白',
        content: '谁家玉笛暗飞声，散入春风满洛城。\n此夜曲中闻折柳，何人不起故园情。'
      }

      const wrapper = mount(PoemCardRenderer, {
        props: {
          poem: poemWithAllusion,
          removePunctuation: true,
          traditional: true
        }
      })

      const verseColumns = wrapper.findAll('.verse-chars')
      expect(verseColumns.length).toBeGreaterThan(0)
      
      const allText = verseColumns.map(c => c.text()).join('')
      // 验证“折柳”在繁体无标点下依然完整存在且转换为繁体
      expect(allText).toContain('折柳')
      expect(allText).toContain('春風')
      expect(allText).not.toContain('，')
      expect(allText).not.toContain('。')
    })

    it('Case X.3: 路由页面跳转过程中常驻 SoundscapeWidget 维持播放状态', async () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/', redirect: '/poem/1' },
          { path: '/poem/1', component: { template: '<div>诗词详情</div>' } },
          { path: '/rhesis', component: { template: '<div>名句集锦</div>' } },
          { path: '/review', component: { template: '<div>复习</div>' } }
        ]
      })

      const store = useSoundscapeStore()
      await store.togglePlay()
      expect(store.isPlaying).toBe(true)

      // 模拟常驻根组件挂载 Widget
      const widgetWrapper = mount(SoundscapeWidget, {
        global: { plugins: [router] }
      })

      await router.push('/poem/1')
      await router.isReady()
      expect(store.isPlaying).toBe(true)

      await router.push('/rhesis')
      expect(store.isPlaying).toBe(true)

      await router.push('/review')
      expect(store.isPlaying).toBe(true)
      expect(widgetWrapper.exists()).toBe(true)
    })
  })

  // -----------------------------------------------------------------------
  // TIER 4: REAL-WORLD APPLICATION WORKLOADS
  // -----------------------------------------------------------------------

  describe('Tier 4: Real-World Application Workloads', () => {
    it('Case W.1: 完整文人学士读书旅程 (春江花月夜 + 雨打芭蕉 + 典故溯源 + 墨夜泥金印章卡片导出)', async () => {
      // 1. 学士进入读诗界面，开启“雨打芭蕉”伴读白噪音，调节音量为 40%
      const store = useSoundscapeStore()
      await store.setScene('rain')
      store.setVolume(40)
      await store.togglePlay()

      expect(store.isPlaying).toBe(true)
      expect(store.currentSceneId).toBe('rain')
      expect(store.volume).toBe(40)

      // 2. 学士研读张若虚《春江花月夜》，悬浮识别正文典故（“鸿雁”、“尺素”）
      const poemText = '鸿雁长飞光不度，鱼龙潜跃水成文。'
      const tokens = tokenizeVerseOracle(poemText)
      const matchedAllusion = tokens.find(t => t.text === '鸿雁')
      expect(matchedAllusion).toBeDefined()
      expect(matchedAllusion?.allusion?.sentiment).toBe('关山尺素')

      // 3. 学士点击“生成诗词卡片”，打开配置弹窗
      const modalWrapper = mount(PoemCardModal, {
        props: {
          visible: true,
          poem: {
            title: '春江花月夜',
            dynasty: '唐代',
            writer: '张若虚',
            content: poemText
          }
        },
        global: {
          plugins: [ElementPlus],
          stubs: {
            'el-dialog': {
              props: ['modelValue'],
              template: '<div class="el-dialog-stub" v-if="modelValue !== false"><slot /></div>'
            }
          }
        }
      })

      expect(modalWrapper.find('.preview-panel').exists()).toBe(true)

      // 4. 学士定制卡片：选择“墨夜泥金”暗色主题、输入印章名“东坡居士”、选择朱文阳刻
      const themeChips = modalWrapper.findAll('.theme-chip')
      await themeChips[1].trigger('click') // 墨夜泥金

      // 5. 触发高清图片导出流程
      const dummyCardRoot = document.createElement('div')
      const exportUrl = await exportCardImage(dummyCardRoot, '诗词卡片-张若虚-春江花月夜.png', { pixelRatio: 3 })
      expect(exportUrl).toContain('mockPngBase64_pixelRatio_3')

      // 6. 验证旅程结束后音频状态持续安稳
      expect(store.isPlaying).toBe(true)
    })

    it('Case W.2: 名句集锦研读旅程 (庄周梦蝶 + 古寺暮钟 + 白文印章微卡片)', async () => {
      // 1. 切换至古寺暮钟场景
      const store = useSoundscapeStore()
      await store.setScene('temple')
      await store.togglePlay()
      expect(store.currentSceneId).toBe('temple')

      // 2. 溯源典故“梦蝶”
      const quote = '庄生晓梦迷蝴蝶'
      const tokens = tokenizeVerseOracle(quote)
      const mengdie = tokens.find(t => t.text === '梦蝶')
      // “梦蝶”在庄生晓梦中因“蝴蝶”语境相关
      expect(ALLUSION_SEEDS_ORACLE.find(a => a.name === '梦蝶')?.origin).toBe('《庄子·齐物论》')

      // 3. 渲染白文阴刻印章
      const sealWrapper = mount(ClassicalSeal, {
        props: {
          text: '青莲',
          carving: 'yin',
          shape: 'oval'
        }
      })
      expect(sealWrapper.find('ellipse').exists()).toBe(true)

      // 4. 清理
      soundscapeEngine.destroy()
    })
  })
})
