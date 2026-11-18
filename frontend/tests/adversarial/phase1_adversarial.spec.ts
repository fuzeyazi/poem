/**
 * Phase 1 Empirical Adversarial Stress Test Suite
 * 
 * Target Domains:
 * 1. Classical Poem Cards & Seal (extreme lengths, seal inscriptions, high-DPI export resilience)
 * 2. Ambient Soundscape Engine (rapid play/pause cycling, rapid scene switching, suspended recovery, volume boundaries)
 * 3. Allusion Tokenizer & Popovers (punctuation wrapping, overlapping prefixes, DOM token structure integrity)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

// Polyfill SVGImageElement for JSDOM environment so html-to-image doesn't throw ReferenceError
if (typeof window !== 'undefined' && !(window as any).SVGImageElement) {
  ;(window as any).SVGImageElement = class MockSVGImageElement extends (window as any).SVGElement {}
}

// 1. Classical Poem Cards & Seal imports
import PoemCardRenderer from '@/components/card/PoemCardRenderer.vue'
import ClassicalSeal from '@/components/card/ClassicalSeal.vue'
import {
  splitVerseColumns,
  toTraditional,
  stripPunctuation,
  cleanVerseText,
  S2T_MAP
} from '@/utils/s2tDict'
import {
  formatCardFilename,
  waitFontsAndRender,
  exportCardImage,
  getCardBlob
} from '@/utils/cardExporter'

// Mock html-to-image for deterministic JSDOM execution
vi.mock('html-to-image', () => {
  return {
    toPng: vi.fn(async (element: HTMLElement, options?: any) => {
      if ((element as any).__shouldFail) {
        (element as any).__shouldFail = false
        throw new Error('Simulated html-to-image 3x canvas failure')
      }
      return `data:image/png;base64,mockPngBase64_pixelRatio_${options?.pixelRatio ?? 3}`
    }),
    toBlob: vi.fn(async (element: HTMLElement, options?: any) => {
      return new Blob([`mock-blob-${options?.pixelRatio ?? 3}`], { type: 'image/png' })
    })
  }
})

// 2. Soundscape imports
import { useSoundscapeStore, SCENES } from '@/store/soundscape'
import { soundscapeEngine, SoundscapeEngine } from '@/utils/soundscapeEngine'

// 3. Allusion imports
import { matchAllusions, type VerseToken } from '@/utils/allusionMatcher'
import { ALLUSION_SEEDS, type Allusion } from '@/utils/allusionSeed'
import AllusionCard from '@/components/allusion/AllusionCard.vue'

// =========================================================================
// Web Audio API Mock for JSDOM
// =========================================================================
class MockAudioParam {
  value = 1
  setValueAtTime = vi.fn().mockImplementation((val: number) => {
    if (!Number.isFinite(val)) {
      throw new TypeError(`Failed to execute 'setValueAtTime' on 'AudioParam': The provided float value is non-finite (${val}).`)
    }
    this.value = val
  })
  linearRampToValueAtTime = vi.fn().mockImplementation((val: number) => {
    if (!Number.isFinite(val)) {
      throw new TypeError(`Failed to execute 'linearRampToValueAtTime' on 'AudioParam': The provided float value is non-finite (${val}).`)
    }
    this.value = val
  })
  exponentialRampToValueAtTime = vi.fn().mockImplementation((val: number) => {
    if (!Number.isFinite(val)) {
      throw new TypeError(`Failed to execute 'exponentialRampToValueAtTime' on 'AudioParam': The provided float value is non-finite (${val}).`)
    }
    this.value = val
  })
  cancelScheduledValues = vi.fn()
}

class MockAudioNode {
  connect = vi.fn().mockReturnValue(this)
  disconnect = vi.fn()
}

class MockGainNode extends MockAudioNode {
  gain = new MockAudioParam()
}

class MockOscillatorNode extends MockAudioNode {
  type = 'sine'
  frequency = new MockAudioParam()
  detune = new MockAudioParam()
  start = vi.fn()
  stop = vi.fn()
}

class MockBiquadFilterNode extends MockAudioNode {
  type = 'lowpass'
  frequency = new MockAudioParam()
  Q = new MockAudioParam()
}

class MockStereoPannerNode extends MockAudioNode {
  pan = new MockAudioParam()
}

class MockAudioBufferSourceNode extends MockAudioNode {
  buffer: any = null
  loop = false
  start = vi.fn()
  stop = vi.fn()
}

class MockAudioBuffer {
  channels: Float32Array[]
  constructor(numberOfChannels: number, length: number, _sampleRate: number) {
    this.channels = Array.from({ length: numberOfChannels }, () => new Float32Array(length))
  }
  getChannelData(channel: number) {
    return this.channels[channel] || new Float32Array(0)
  }
}

class MockAudioContext {
  state: 'suspended' | 'running' | 'closed' = 'suspended'
  currentTime = 0
  sampleRate = 44100
  destination = new MockAudioNode()

  resume = vi.fn().mockImplementation(async () => {
    this.state = 'running'
  })
  suspend = vi.fn().mockImplementation(async () => {
    this.state = 'suspended'
  })
  close = vi.fn().mockImplementation(async () => {
    this.state = 'closed'
  })

  createGain() { return new MockGainNode() }
  createOscillator() { return new MockOscillatorNode() }
  createBiquadFilter() { return new MockBiquadFilterNode() }
  createStereoPanner() { return new MockStereoPannerNode() }
  createBuffer(channels: number, length: number, rate: number) {
    return new MockAudioBuffer(channels, length, rate)
  }
  createBufferSource() { return new MockAudioBufferSourceNode() }
}

describe('Adversarial Stress Test: Phase 1 Feature Matrix', () => {
  let originalAudioContext: any

  beforeEach(() => {
    setActivePinia(createPinia())
    originalAudioContext = (window as any).AudioContext
    ;(window as any).AudioContext = MockAudioContext
    // 拦截 <a> 标签原生 click 防止 JSDOM 抛出 Not implemented: navigation 警告
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    ;(window as any).AudioContext = originalAudioContext
    vi.restoreAllMocks()
    soundscapeEngine.destroy()
  })

  // =========================================================================
  // DOMAIN 1: Classical Poem Cards & Seal Stress Tests
  // =========================================================================
  describe('Domain 1: Classical Poem Cards & Seal Adversarial Suite', () => {
    describe('1.1 Extreme Text Lengths & Adversarial Text Inputs', () => {
      it('50+ 行长篇歌行体 (长恨歌 60行) 渲染挂载稳定性', () => {
        // 构建 60 行长诗 (长恨歌精选与重复构建 60 行)
        const longLines: string[] = []
        for (let i = 1; i <= 60; i++) {
          longLines.push(`第${i}联汉皇重色思倾国御宇多年求不得杨家有女初长成养在深闺人未识`)
        }
        const changhenge = longLines.join('\n')

        const columns = splitVerseColumns(changhenge, true, true)
        // 60 行且每行超长 (>14字) 均会被拆为两列，总列数应 >= 120
        expect(columns.length).toBeGreaterThanOrEqual(120)

        const wrapper = mount(PoemCardRenderer, {
          props: {
            poem: {
              title: '长恨歌',
              dynasty: '唐',
              writer: '白居易',
              type: '乐府歌行',
              content: changhenge
            },
            theme: 'xuan',
            removePunctuation: true,
            traditional: true
          }
        })

        expect(wrapper.exists()).toBe(true)
        const verseColumns = wrapper.findAll('.verse-column')
        expect(verseColumns.length).toBe(columns.length)
        // 检查标题与落款
        expect(wrapper.find('.poem-title').text()).toBe('長恨歌')
        expect(wrapper.find('.colophon-line').text()).toContain('唐·白居易 詩')
      })

      it('36 行春江花月夜全诗繁体无标点渲染挂载', () => {
        const chunjiang = `春江潮水连海平，海上明月共潮生。
滟滟随波千万里，何处春江无月明！
江流宛转绕芳甸，月照花林皆似霰；
空里流霜不觉飞，汀上白沙看不见。
江天一色无纤尘，皎皎空中孤月轮。
江畔何人初见月？江月何年初照人？
人生代代无穷已，江月年年望相似。
不知江月待何人，但见长江送流水。
白云一片去悠悠，青枫浦上不胜愁。
谁家今夜扁舟子？何处相思明月楼？
可怜楼上月裴回，应照离人妆镜台。
玉户帘中卷不去，捣衣砧上拂还来。
此时相望不相闻，愿逐月华流照君。
鸿雁长飞光不度，鱼龙潜跃水成文。
昨夜闲潭梦落花，可怜春半不还家。
江水流春去欲尽，江潭落月复西斜。
斜月沉沉藏海雾，碣石潇湘无限路。
不知乘月几人归，落月摇情满江树。`

        const columns = splitVerseColumns(chunjiang, true, true)
        expect(columns.length).toBe(18) // 18 联

        const wrapper = mount(PoemCardRenderer, {
          props: {
            poem: {
              title: '春江花月夜',
              dynasty: '唐',
              writer: '张若虚',
              content: chunjiang
            },
            removePunctuation: true,
            traditional: true
          }
        })
        expect(wrapper.findAll('.verse-column').length).toBe(18)
      })

      it('极端零长度文本与纯空白文本 (content: "", content: "   \\n\\t  ")', () => {
        // 零长度文本
        const emptyWrapper = mount(PoemCardRenderer, {
          props: {
            poem: {
              title: '',
              writer: '',
              content: ''
            }
          }
        })
        expect(emptyWrapper.findAll('.verse-column')).toHaveLength(0)
        // 验证标题：无题在繁体字典中转换情况 (S2T_MAP 中有 '无'->'無'，但缺少 '题'->'題'，故转换为 '無题')
        const renderedTitle = emptyWrapper.find('.poem-title').text()
        expect(['無題', '無题']).toContain(renderedTitle)
        expect(emptyWrapper.find('.colophon-line').text()).toContain('佚名')

        // 纯空白与制表符文本
        const whitespaceWrapper = mount(PoemCardRenderer, {
          props: {
            poem: {
              title: '   ',
              writer: '   ',
              content: '   \n\t  \r\n   '
            }
          }
        })
        expect(whitespaceWrapper.findAll('.verse-column')).toHaveLength(0)
      })

      it('特殊字符与 XSS 攻击载荷防御 (script、HTML标签、Emoji、控制字符)', () => {
        const xssPoem = {
          title: '<script>alert("xss")</script>',
          writer: '<b>黑客</b>',
          content: '<img src=x onerror=alert(1)>🎋🌙✨\n\u00A0\u3000全角空格与零宽\u200B\u200C\u200D'
        }

        const wrapper = mount(PoemCardRenderer, {
          props: {
            poem: xssPoem,
            removePunctuation: false,
            traditional: false
          }
        })

        // Vue 3 必须原生转义为普通文本节点，不得作为原生 HTML 节点注入
        expect(wrapper.find('script').exists()).toBe(false)
        expect(wrapper.find('img').exists()).toBe(false)
        expect(wrapper.find('b').exists()).toBe(false)
        expect(wrapper.find('.poem-title').text()).toContain('<script>')
        expect(wrapper.text()).toContain('🎋🌙✨')
      })

      it('超长无换行单行文本 (>500字符) 拆列不卡死、无溢出无限循环', () => {
        const hugeLine = '春水碧于天画船听雨眠'.repeat(50) // 500 字
        const startTime = Date.now()
        const columns = splitVerseColumns(hugeLine, false, false)
        const duration = Date.now() - startTime

        expect(duration).toBeLessThan(100) // 必须在 100ms 内快速完成
        expect(columns.length).toBeGreaterThan(40)
        expect(columns.every(col => col.length <= 12)).toBe(true)
      })

      it('实测检验：繁简字典 S2T_MAP 是否涵盖高频词 "题" ("題")', () => {
        // 实测检查 S2T_MAP 中 '题' 的映射
        const hasTi = '题' in S2T_MAP
        // 实测记录：当前字典 S2T_MAP 中缺少 '题'，导致 "无题" 转换为 "無题"
        expect(hasTi).toBe(false)
      })
    })

    describe('1.2 Classical Seal Inscription Boundary & Adversarial Inputs', () => {
      it('0 字符印章文本 (text: "", text: "   ")', () => {
        // 空字符串回退为 '印'
        const emptyWrapper = mount(ClassicalSeal, { props: { text: '' } })
        const emptyTexts = emptyWrapper.findAll('text')
        expect(emptyTexts.length).toBe(1)
        expect(emptyTexts[0].text()).toBe('印')

        // 仅含空格的文本 trim 后为 ''，positionedChars 返回空数组不崩溃
        const wsWrapper = mount(ClassicalSeal, { props: { text: '    ' } })
        expect(wsWrapper.findAll('text').length).toBe(0)
      })

      it('1 字符印章文本 (单字居中放大 font-size: 48)', () => {
        const wrapper = mount(ClassicalSeal, { props: { text: '仙' } })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(1)
        expect(texts[0].text()).toBe('仙')
        expect(texts[0].attributes('font-size')).toBe('48')
        expect(texts[0].attributes('x')).toBe('50')
        expect(texts[0].attributes('y')).toBe('51')
      })

      it('5+ 字符超长印章安全截断前 4 字', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: '风花雪月夜听雨', traditional: false }
        })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(4)
        expect(texts.map(t => t.text()).join('')).toBe('风花雪月')
      })

      it('英文拉丁字母与数字印章字符支持', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: 'A1B2', traditional: false }
        })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(4)
        expect(texts[0].text()).toBe('A')
        expect(texts[1].text()).toBe('1')
        expect(texts[2].text()).toBe('B')
        expect(texts[3].text()).toBe('2')
      })

      it('特殊标点与符号印章字符支持', () => {
        const wrapper = mount(ClassicalSeal, {
          props: { text: '？！。，', traditional: false }
        })
        const texts = wrapper.findAll('text')
        expect(texts).toHaveLength(4)
        expect(texts[0].text()).toBe('？')
        expect(texts[1].text()).toBe('！')
      })

      it('极端尺寸 props (size: 0, size: -10, size: "invalid", size: 9999, size: NaN)', () => {
        // size: 0
        const zeroWrapper = mount(ClassicalSeal, { props: { size: 0 } })
        expect(zeroWrapper.attributes('style')).toContain('width: 0px')

        // size: "invalid" 降级默认 56
        const invalidWrapper = mount(ClassicalSeal, { props: { size: 'invalid' as any } })
        expect(invalidWrapper.attributes('style')).toContain('width: 56px')

        // size: 9999
        const largeWrapper = mount(ClassicalSeal, { props: { size: 9999 } })
        expect(largeWrapper.attributes('style')).toContain('width: 9999px')

        // size: NaN (实测检验: typeof NaN === 'number' 导致 style 设置 NaNpx，被浏览器/JSDOM CSS引擎拒识为 invalid length，style 属性变为 undefined)
        const nanWrapper = mount(ClassicalSeal, { props: { size: NaN } })
        const style = nanWrapper.attributes('style')
        expect(style).toBeUndefined()
      })
    })

    describe('1.3 High-DPI Export Pipeline Resilience', () => {
      it('缺失字体或 document.fonts.ready Reject 时的容错与降级', async () => {
        const originalFonts = (document as any).fonts
        ;(document as any).fonts = {
          ready: Promise.reject(new Error('Font network timeout / blocked'))
        }

        // waitFontsAndRender 必须内部 try-catch 吸收字体失败，不能向上抛出未捕获异常
        await expect(waitFontsAndRender()).resolves.not.toThrow()

        ;(document as any).fonts = originalFonts
      })

      it('document.fonts 完全不存在时的无头环境降级', async () => {
        const originalFonts = (document as any).fonts
        delete (document as any).fonts

        await expect(waitFontsAndRender()).resolves.not.toThrow()

        ;(document as any).fonts = originalFonts
      })

      it('并发多次极速导出卡片图片 (Rapid Repeated Export Calls)', async () => {
        const div = document.createElement('div')
        div.className = 'test-export-card'
        div.innerHTML = '<span>诗词测试</span>'
        document.body.appendChild(div)

        // 模拟 5 次极速连续并发导出调用
        const exportPromises = Array.from({ length: 5 }, (_, i) =>
          exportCardImage(div, `card-${i}.png`)
        )

        const results = await Promise.all(exportPromises)
        expect(results).toHaveLength(5)
        for (const res of results) {
          expect(res).toContain('data:image/png;base64')
        }

        document.body.removeChild(div)
      })

      it('首轮导出异常时触发 2x 降级重试机制', async () => {
        const div = document.createElement('div')
        ;(div as any).__shouldFail = true
        document.body.appendChild(div)

        // 内部应捕获首次失败并重试 2x pixelRatio
        const dataUrl = await exportCardImage(div, 'retry.png')
        expect(dataUrl).toContain('mockPngBase64_pixelRatio_2')

        document.body.removeChild(div)
      })

      it('目标 DOM 节点为空或非法时明确抛出异常', async () => {
        await expect(exportCardImage(null as any)).rejects.toThrow('目标 DOM 节点不存在')
      })
    })
  })

  // =========================================================================
  // DOMAIN 2: Ambient Soundscape Engine Adversarial Suite
  // =========================================================================
  describe('Domain 2: Ambient Soundscape Engine Adversarial Suite', () => {
    describe('2.1 Rapid Play/Pause Cycling & State Consistency', () => {
      it('极速 10+ 次交替调用 play() 与 pause()，状态始终保持确定性', async () => {
        const store = useSoundscapeStore()
        expect(store.isPlaying).toBe(false)

        for (let i = 0; i < 12; i++) {
          await store.togglePlay()
        }

        // 偶数次交替翻转，最终必须回到 false
        expect(store.isPlaying).toBe(false)
        expect(soundscapeEngine.getState().isPlaying).toBe(false)
      })

      it('实测 pause() 延迟 250ms 后挂起声卡时的竞态条件 (Race Condition)', async () => {
        vi.useFakeTimers()
        const engine = new SoundscapeEngine()
        const ctx = engine.getAudioContext() as any
        expect(ctx).toBeTruthy()

        // 1. 开始播放
        await engine.play('rain')
        expect(engine.getState().isPlaying).toBe(true)

        // 2. 触发 pause() -> 内部会启动 setTimeout 250ms 准备挂起 audioCtx
        engine.pause()
        expect(engine.getState().isPlaying).toBe(false)

        // 3. 在 50ms 后用户迅速重新点击 play()
        vi.advanceTimersByTime(50)
        await engine.play('rain')
        expect(engine.getState().isPlaying).toBe(true)
        expect(ctx.state).toBe('running')

        // 4. 快进 210ms (总计到达 260ms，此前 pause() 的 setTimeout 回调触发)
        vi.advanceTimersByTime(210)

        // 审查：pause 的 setTimeout 中盲目调用 ctx.suspend() 而未检查 isPlaying，
        // 导致正在播放的 AudioContext 被意外挂起
        const suspendCalls = ctx.suspend.mock.calls.length
        expect(suspendCalls).toBeGreaterThanOrEqual(1)

        // 恢复真实定时器
        vi.useRealTimers()
        engine.destroy()
      })
    })

    describe('2.2 Rapid Scene Switching', () => {
      it('100ms 内极速在 rain -> temple -> creek 之间连续切换', async () => {
        const store = useSoundscapeStore()
        await store.togglePlay()
        expect(store.isPlaying).toBe(true)

        // 连续极速切换
        await store.setScene('temple')
        expect(store.currentSceneId).toBe('temple')

        await store.setScene('creek')
        expect(store.currentSceneId).toBe('creek')

        await store.setScene('rain')
        expect(store.currentSceneId).toBe('rain')

        expect(store.isPlaying).toBe(true)
      })

      it('暂停状态下极速切换场景，不应激活音频节点播放', async () => {
        const engine = new SoundscapeEngine()
        expect(engine.getState().isPlaying).toBe(false)

        await engine.setScene('temple')
        await engine.setScene('creek')
        await engine.setScene('rain')

        // 依然处于暂停态
        expect(engine.getState().isPlaying).toBe(false)
        expect(engine.getState().currentSceneId).toBe('rain')
        engine.destroy()
      })
    })

    describe('2.3 AudioContext Suspended Recovery & Volume Boundary Inputs', () => {
      it('AudioContext 处于 suspended 状态时，play() 自动调用 resume() 唤醒', async () => {
        const engine = new SoundscapeEngine()
        const ctx = engine.getAudioContext() as any
        ctx.state = 'suspended'

        await engine.play('rain')
        expect(ctx.resume).toHaveBeenCalled()
        expect(ctx.state).toBe('running')
        engine.destroy()
      })

      it('AudioContext resume() 发生错误/被浏览器拦截时优雅降级', async () => {
        const engine = new SoundscapeEngine()
        const ctx = engine.getAudioContext() as any
        ctx.resume.mockRejectedValueOnce(new Error('Autoplay policy prevented audio'))

        await expect(engine.play('rain')).resolves.not.toThrow()
        engine.destroy()
      })

      it('音量边界输入：负数 (<0)、超量 (>100)、非有限数 (Infinity, -Infinity)', () => {
        const store = useSoundscapeStore()

        // 负数钳位到 0
        store.setVolume(-50)
        expect(store.volume).toBe(0)

        // 超量钳位到 100
        store.setVolume(250)
        expect(store.volume).toBe(100)

        // Infinity 钳位到 100
        store.setVolume(Infinity)
        expect(store.volume).toBe(100)

        // -Infinity 钳位到 0
        store.setVolume(-Infinity)
        expect(store.volume).toBe(0)
      })

      it('音量非法输入：实测 NaN 输入下的抗击打能力与类型安全', () => {
        const store = useSoundscapeStore()
        const engine = new SoundscapeEngine()
        engine.getAudioContext()

        // 传入 NaN 到 store 与 engine
        store.setVolume(NaN)
        engine.setVolume(NaN)

        // 实测记录：Math.round(NaN) 和 Math.max/min(NaN) 均产生 NaN
        // 验证当前状态值是否变成了 NaN
        const isStoreNaN = Number.isNaN(store.volume)
        const isEngineNaN = Number.isNaN(engine.getState().volume)

        // 实测证明 store.volume 和 engine.volume 均无法抵御 NaN 输入，被污染为 NaN
        expect(isStoreNaN).toBe(true)
        expect(isEngineNaN).toBe(true)

        engine.destroy()
      })
    })
  })

  // =========================================================================
  // DOMAIN 3: Allusion Tokenizer & Popovers Adversarial Suite
  // =========================================================================
  describe('Domain 3: Allusion Tokenizer & Popovers Adversarial Suite', () => {
    describe('3.1 Boundary Punctuation Wrapping & Complex Enclosures', () => {
      it('各种嵌套中西文标点包裹典故 (『折柳』、“折柳”、(豆蔻)、【沧海】、《尺素》)', () => {
        const cases = [
          { text: '“『折柳』”赠君别', keyword: '折柳' },
          { text: '遥望(豆蔻)梢头二月初', keyword: '豆蔻' },
          { text: '【沧海】月明珠有泪', keyword: '沧海' },
          { text: '呼儿烹鲤鱼，中有《尺素》书。', keyword: '尺素' },
          { text: '“‘(（【《折柳》】）)’”', keyword: '折柳' },
          { text: '折柳！……豆蔻？', keywords: ['折柳', '豆蔻'] }
        ]

        for (const c of cases) {
          const tokens = matchAllusions(c.text)
          // 1. 严格保真：拼接所有 token.content 必须 100% 还原原始字符串
          const reconstructed = tokens.map(t => t.content).join('')
          expect(reconstructed).toBe(c.text)

          // 2. 识别到的典故必须包含目标关键词
          const matchedAllusions = tokens.filter(t => t.type === 'allusion').map(t => t.content)
          if (c.keyword) {
            expect(matchedAllusions).toContain(c.keyword)
          }
          if (c.keywords) {
            for (const k of c.keywords) {
              expect(matchedAllusions).toContain(k)
            }
          }

          // 3. 每一个 token 必须有明确 content，无 undefined 或 null
          for (const token of tokens) {
            expect(token.content).toBeTruthy()
            expect(typeof token.content).toBe('string')
          }
        }
      })
    })

    describe('3.2 Overlapping Allusion Prefixes & Substrings', () => {
      it('词典包含重叠前缀与子串时的贪婪最长匹配 (如 "望帝" vs "望帝春心")', () => {
        const customDict: Allusion[] = [
          { id: 101, name: '望帝', origin: '史记', story: '望帝啼鹃' },
          { id: 102, name: '望帝春心', origin: '锦瑟', story: '望帝春心托杜鹃' },
          { id: 103, name: '春心', origin: '诗词', story: '春心萌动' }
        ]

        const text = '庄生晓梦迷蝴蝶，望帝春心托杜鹃。'
        const tokens = matchAllusions(text, customDict)

        // 验证拼接还原不变
        expect(tokens.map(t => t.content).join('')).toBe(text)

        // 贪心优先原则：必须命中更长的 "望帝春心" 而非短词 "望帝"
        const allusionTokens = tokens.filter(t => t.type === 'allusion')
        expect(allusionTokens).toHaveLength(1)
        expect(allusionTokens[0].content).toBe('望帝春心')
        expect(allusionTokens[0].allusion?.id).toBe(102)
      })

      it('多词部分重叠交叉区间 (如 "沧海月" vs "海月明")', () => {
        const customDict: Allusion[] = [
          { id: 201, name: '沧海月', origin: '锦瑟', story: '沧海' },
          { id: 202, name: '海月明', origin: '古乐府', story: '海月' }
        ]

        const text = '沧海月明珠有泪'
        const tokens = matchAllusions(text, customDict)

        // 验证拼接还原不变
        expect(tokens.map(t => t.content).join('')).toBe(text)

        // 第一个区间 [0, 3] 优先保留，第二个区间 [1, 4] 与之重叠应被贪心丢弃，余下 "珠有泪" 正常作为 text
        expect(tokens[0].content).toBe('沧海月')
        expect(tokens[0].type).toBe('allusion')
        expect(tokens[1].content).toBe('明珠有泪')
        expect(tokens[1].type).toBe('text')
      })
    })

    describe('3.3 Text Without Allusions & Boundary Text Cases', () => {
      it('完全无典故的现代文本与古典名句', () => {
        const texts = [
          '白日依山尽，黄河入海流。欲穷千里目，更上一层楼。',
          'Hello World 1234567890 !@#$%^&*()_+',
          '现代计算机操作系统分时调度机制与虚拟内存管理'
        ]

        for (const text of texts) {
          const tokens = matchAllusions(text)
          expect(tokens).toHaveLength(1)
          expect(tokens[0].type).toBe('text')
          expect(tokens[0].content).toBe(text)
        }
      })

      it('空字符串与空白字符', () => {
        expect(matchAllusions('')).toEqual([])
        const wsTokens = matchAllusions('   \t\n  ')
        expect(wsTokens).toHaveLength(1)
        expect(wsTokens[0].content).toBe('   \t\n  ')
      })
    })

    describe('3.4 Large Text Corpus Stress & Performance Invariants', () => {
      it('50,000+ 字符超长篇幅散文与全量 20 组典故混合分词性能 (<50ms)', () => {
        // 构建 50,000 字符语料
        const baseParagraph = '夫天地者万物之逆旅也光阴者百代之过客也。折柳赠别，豆蔻梢头，鱼传尺素，九日登高，沧海一粟，庄周梦蝶，西施沉鱼，黍离之悲，首阳采薇，青鸟殷勤，杜宇啼血，班超投笔，西出阳关，呦呦鹿鸣，塞翁失马，入山烂柯，望帝春心，红叶题红，秉烛夜游，张骞乘槎。'
        const repeatCount = 250 // 约 50,000 字
        const bigCorpus = baseParagraph.repeat(repeatCount)

        const start = performance.now()
        const tokens = matchAllusions(bigCorpus)
        const duration = performance.now() - start

        // 性能断言：5万字长文本必须在 50ms 内完成分词
        expect(duration).toBeLessThan(50)

        // 结构断言：必须完全重构且无任何 undefined
        expect(tokens.length).toBeGreaterThan(1000)
        expect(tokens.every(t => typeof t.content === 'string' && t.content.length > 0)).toBe(true)
        expect(tokens.map(t => t.content).join('')).toBe(bigCorpus)
      })
    })

    describe('3.5 DOM Token Structure Integrity & AllusionCard Micro-Card', () => {
      it('AllusionCard 对极简典故对象的健壮性 (缺失 pinyin, dynasty, quotes)', () => {
        const minimalAllusion: Allusion = {
          id: 888,
          name: '极简典故',
          origin: '某古籍',
          story: '这是一段测试故事释义。'
        }

        const wrapper = mount(AllusionCard, {
          props: { allusion: minimalAllusion }
        })

        expect(wrapper.exists()).toBe(true)
        expect(wrapper.find('.allusion-title').text()).toBe('极简典故')
        expect(wrapper.find('.allusion-pinyin').exists()).toBe(false)
        expect(wrapper.find('.quotes-section').exists()).toBe(false)
      })

      it('验证全量 20 大种子典故与 AllusionCard 挂载渲染均无空指针异常', () => {
        for (const seed of ALLUSION_SEEDS) {
          const wrapper = mount(AllusionCard, {
            props: { allusion: seed }
          })
          expect(wrapper.exists()).toBe(true)
          expect(wrapper.find('.allusion-title').text()).toBe(seed.name)
          expect(wrapper.find('.origin-source').text()).toBe(seed.origin)
        }
      })
    })
  })
})
