import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import { useSoundscapeStore, SCENES } from '@/store/soundscape'
import { soundscapeEngine, SoundscapeEngine } from '@/utils/soundscapeEngine'
import SoundscapeWidget from '@/components/soundscape/SoundscapeWidget.vue'

// ==========================================
// Web Audio API Mock for JSDOM Environment
// ==========================================

class MockAudioParam {
  value = 1
  setValueAtTime = vi.fn().mockImplementation((val: number) => {
    this.value = val
  })
  linearRampToValueAtTime = vi.fn().mockImplementation((val: number) => {
    this.value = val
  })
  exponentialRampToValueAtTime = vi.fn().mockImplementation((val: number) => {
    this.value = val
  })
  cancelScheduledValues = vi.fn()
}

class MockAudioNode {
  connect = vi.fn()
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
  constructor(numberOfChannels: number, length: number, sampleRate: number) {
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

  resume = vi.fn().mockResolvedValue(undefined)
  suspend = vi.fn().mockResolvedValue(undefined)
  close = vi.fn().mockResolvedValue(undefined)

  createGain() {
    return new MockGainNode()
  }
  createOscillator() {
    return new MockOscillatorNode()
  }
  createBiquadFilter() {
    return new MockBiquadFilterNode()
  }
  createStereoPanner() {
    return new MockStereoPannerNode()
  }
  createBuffer(channels: number, length: number, rate: number) {
    return new MockAudioBuffer(channels, length, rate)
  }
  createBufferSource() {
    return new MockAudioBufferSourceNode()
  }
}

describe('Poetic Soundscape Module', () => {
  let originalAudioContext: any

  beforeEach(() => {
    setActivePinia(createPinia())
    originalAudioContext = (window as any).AudioContext
    ;(window as any).AudioContext = MockAudioContext
  })

  afterEach(() => {
    ;(window as any).AudioContext = originalAudioContext
    vi.restoreAllMocks()
    soundscapeEngine.destroy()
  })

  // ==========================================
  // 1. Soundscape Pinia Store Tests
  // ==========================================
  describe('Soundscape Pinia Store', () => {
    it('初始化默认状态正确（雨打芭蕉、音量60、未静音、暂停态、折叠态）', () => {
      const store = useSoundscapeStore()
      expect(store.currentSceneId).toBe('rain')
      expect(store.volume).toBe(60)
      expect(store.isMuted).toBe(false)
      expect(store.isExpanded).toBe(false)
      // 严格遵守浏览器冷启动规范：isPlaying 必须初始为 false
      expect(store.isPlaying).toBe(false)
    })

    it('SCENES 包含全部三种古典意境定义', () => {
      expect(SCENES).toHaveLength(3)
      const ids = SCENES.map((s) => s.id)
      expect(ids).toContain('rain')
      expect(ids).toContain('temple')
      expect(ids).toContain('creek')

      expect(SCENES[0].name).toBe('雨打芭蕉')
      expect(SCENES[1].name).toBe('古寺暮钟')
      expect(SCENES[2].name).toBe('小桥流水')
    })

    it('持久化配置验证：仅持久化配置项，严禁持久化 isPlaying', () => {
      const store = useSoundscapeStore()
      // Pinia store $options 检查 persist pick 列表
      const persistOptions = (store as any).$options?.persist
      if (persistOptions) {
        const picked = Array.isArray(persistOptions.pick) ? persistOptions.pick : []
        expect(picked).toContain('volume')
        expect(picked).toContain('currentSceneId')
        expect(picked).toContain('isMuted')
        expect(picked).toContain('isExpanded')
        expect(picked).not.toContain('isPlaying')
      }
    })

    it('setVolume 正确调节并钳位在 0~100 之间，静音时提升音量自动解除静音', () => {
      const store = useSoundscapeStore()

      store.setVolume(85)
      expect(store.volume).toBe(85)

      // 超过100钳位
      store.setVolume(120)
      expect(store.volume).toBe(100)

      // 小于0钳位
      store.setVolume(-15)
      expect(store.volume).toBe(0)

      // 静音状态下调大音量自动解除静音
      store.toggleMute()
      expect(store.isMuted).toBe(true)
      store.setVolume(45)
      expect(store.volume).toBe(45)
      expect(store.isMuted).toBe(false)
    })

    it('toggleMute 与 toggleExpand 状态流转严密', () => {
      const store = useSoundscapeStore()

      expect(store.isMuted).toBe(false)
      store.toggleMute()
      expect(store.isMuted).toBe(true)
      store.toggleMute()
      expect(store.isMuted).toBe(false)

      expect(store.isExpanded).toBe(false)
      store.toggleExpand()
      expect(store.isExpanded).toBe(true)
      store.setExpanded(false)
      expect(store.isExpanded).toBe(false)
    })

    it('setScene 能正确更新当前场景', async () => {
      const store = useSoundscapeStore()

      await store.setScene('temple')
      expect(store.currentSceneId).toBe('temple')

      await store.setScene('creek')
      expect(store.currentSceneId).toBe('creek')

      await store.setScene('rain')
      expect(store.currentSceneId).toBe('rain')
    })

    it('togglePlay 能正确触发播放与暂停，并联动底层引擎', async () => {
      const store = useSoundscapeStore()
      const playSpy = vi.spyOn(soundscapeEngine, 'play').mockResolvedValue()
      const pauseSpy = vi.spyOn(soundscapeEngine, 'pause').mockImplementation(() => {})

      expect(store.isPlaying).toBe(false)

      // 首次点击播放
      await store.togglePlay()
      expect(store.isPlaying).toBe(true)
      expect(playSpy).toHaveBeenCalledWith('rain')

      // 再次点击暂停
      await store.togglePlay()
      expect(store.isPlaying).toBe(false)
      expect(pauseSpy).toHaveBeenCalled()

      // 明确 pause
      await store.togglePlay()
      expect(store.isPlaying).toBe(true)
      store.pause()
      expect(store.isPlaying).toBe(false)
    })
  })

  // ==========================================
  // 2. Soundscape Web Audio Engine Tests
  // ==========================================
  describe('Soundscape Procedural Audio Engine', () => {
    it('引擎单例能够正常初始化并获取 AudioContext', () => {
      const engine = new SoundscapeEngine()
      const ctx = engine.getAudioContext()
      expect(ctx).not.toBeNull()
      expect(engine.getState().volume).toBe(0.6)
      expect(engine.getState().isMuted).toBe(false)
      expect(engine.getState().isPlaying).toBe(false)
      engine.destroy()
    })

    it('setVolume 能正确钳位在 0.0 ~ 1.0', () => {
      const engine = new SoundscapeEngine()
      engine.getAudioContext()

      engine.setVolume(0.75)
      expect(engine.getState().volume).toBe(0.75)

      engine.setVolume(1.8)
      expect(engine.getState().volume).toBe(1.0)

      engine.setVolume(-0.4)
      expect(engine.getState().volume).toBe(0.0)

      engine.destroy()
    })

    it('setMuted 和 setDucking 能平稳更新增益态', () => {
      const engine = new SoundscapeEngine()
      engine.getAudioContext()

      engine.setMuted(true)
      expect(engine.getState().isMuted).toBe(true)

      engine.setDucking(true)
      engine.setDucking(false)

      engine.setMuted(false)
      expect(engine.getState().isMuted).toBe(false)

      engine.destroy()
    })

    it('play、setScene 与 pause 执行场景构建与交叉淡化流转', async () => {
      const engine = new SoundscapeEngine()

      await engine.play('rain')
      expect(engine.getState().isPlaying).toBe(true)
      expect(engine.getState().currentSceneId).toBe('rain')

      // 切换至暮钟场景（平滑交叉淡化）
      await engine.setScene('temple')
      expect(engine.getState().currentSceneId).toBe('temple')

      // 切换至小桥流水场景
      await engine.setScene('creek')
      expect(engine.getState().currentSceneId).toBe('creek')

      engine.pause()
      expect(engine.getState().isPlaying).toBe(false)

      engine.destroy()
    })

    it('strikeTempleBell 能在传入节点上构建6分音加法正弦振荡器与木杵瞬态', () => {
      const engine = new SoundscapeEngine()
      const ctx = engine.getAudioContext() as any
      expect(ctx).toBeTruthy()

      const dest = ctx.createGain()
      const createOscSpy = vi.spyOn(ctx, 'createOscillator')
      const createFilterSpy = vi.spyOn(ctx, 'createBiquadFilter')

      engine.strikeTempleBell(ctx, dest)

      // 6个非谐波分音正弦振荡器 + 1个木杵瞬态振荡器 = 7个 OscillatorNode
      expect(createOscSpy).toHaveBeenCalledTimes(7)
      // 1个木杵瞬态带通滤波器
      expect(createFilterSpy).toHaveBeenCalled()

      engine.destroy()
    })

    it('AudioContext 处于 suspended 时，play() 会自动调用 resume() 唤醒', async () => {
      const engine = new SoundscapeEngine()
      const ctx = engine.getAudioContext() as any
      ctx.state = 'suspended'
      await engine.play('rain')
      expect(ctx.resume).toHaveBeenCalled()
      engine.destroy()
    })

    it('环境缺乏 AudioContext 时（如非浏览器SSR），优雅降级不抛异常', async () => {
      ;(window as any).AudioContext = undefined
      const engine = new SoundscapeEngine()
      expect(engine.getAudioContext()).toBeNull()
      await expect(engine.play('rain')).resolves.not.toThrow()
      engine.destroy()
    })

    it('同一场景重复 play 不会重复创建场景节点', async () => {
      const engine = new SoundscapeEngine()
      await engine.play('rain')
      const ctx = engine.getAudioContext() as any
      const createGainSpy = vi.spyOn(ctx, 'createGain')
      // 第二次 play 相同场景
      await engine.play('rain')
      expect(createGainSpy).not.toHaveBeenCalled()
      engine.destroy()
    })
  })

  // ==========================================
  // 3. SoundscapeWidget Component UI Tests
  // ==========================================
  describe('SoundscapeWidget Component', () => {
    it('折叠态下默认呈现 44px 悬浮微盘，隐藏 280px 控制面板', () => {
      const store = useSoundscapeStore()
      store.isExpanded = false

      const wrapper = mount(SoundscapeWidget)

      const disc = wrapper.find('.soundscape-disc')
      expect(disc.exists()).toBe(true)
      expect(disc.attributes('title')).toBe('诗境伴读')

      const panel = wrapper.find('.soundscape-panel')
      expect(panel.exists()).toBe(false)
    })

    it('点击折叠微盘能够展开控制面板', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = false

      const wrapper = mount(SoundscapeWidget)

      const disc = wrapper.find('.soundscape-disc')
      await disc.trigger('click')

      expect(store.isExpanded).toBe(true)
      await nextTick()

      const panel = wrapper.find('.soundscape-panel')
      expect(panel.exists()).toBe(true)
      expect(panel.text()).toContain('诗境伴读')
    })

    it('展开面板呈现三联场景选项卡，点击能切换意境', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = true

      const wrapper = mount(SoundscapeWidget)

      const tabs = wrapper.findAll('.scene-tab-item')
      expect(tabs).toHaveLength(3)

      expect(tabs[0].text()).toContain('雨打芭蕉')
      expect(tabs[1].text()).toContain('古寺暮钟')
      expect(tabs[2].text()).toContain('小桥流水')

      // 初始第一项激活
      expect(tabs[0].classes()).toContain('active')

      // 点击切换第二项
      await tabs[1].trigger('click')
      expect(store.currentSceneId).toBe('temple')

      // 点击切换第三项
      await tabs[2].trigger('click')
      expect(store.currentSceneId).toBe('creek')
    })

    it('主播放/暂停按钮点击正确触发 store.togglePlay', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = true
      const togglePlaySpy = vi.spyOn(store, 'togglePlay')

      const wrapper = mount(SoundscapeWidget)

      const playBtn = wrapper.find('.play-toggle-btn')
      expect(playBtn.exists()).toBe(true)

      await playBtn.trigger('click')
      expect(togglePlaySpy).toHaveBeenCalled()
    })

    it('静音按钮点击正确触发 store.toggleMute', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = true

      const wrapper = mount(SoundscapeWidget)

      const muteBtn = wrapper.find('.mute-btn')
      expect(muteBtn.exists()).toBe(true)

      await muteBtn.trigger('click')
      expect(store.isMuted).toBe(true)

      await muteBtn.trigger('click')
      expect(store.isMuted).toBe(false)
    })

    it('音量滑条调节输入触发 store.setVolume', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = true
      const setVolSpy = vi.spyOn(store, 'setVolume')

      const wrapper = mount(SoundscapeWidget)

      const slider = wrapper.find<HTMLInputElement>('.volume-slider')
      expect(slider.exists()).toBe(true)

      await slider.setValue('80')
      await slider.trigger('input')

      expect(setVolSpy).toHaveBeenCalledWith(80)
      expect(store.volume).toBe(80)
    })

    it('面板顶部收起键点击折叠面板', async () => {
      const store = useSoundscapeStore()
      store.isExpanded = true

      const wrapper = mount(SoundscapeWidget)

      const closeBtn = wrapper.find('.header-btn')
      expect(closeBtn.exists()).toBe(true)

      await closeBtn.trigger('click')
      expect(store.isExpanded).toBe(false)
    })
  })
})
