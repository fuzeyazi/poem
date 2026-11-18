/**
 * 诗境伴读过程化 Web Audio API 声学合成引擎 (Soundscape Synthesis Engine)
 * 纯算法过程化合成，100% 零外部音频文件依赖，高保真中式古典意境。
 *
 * 场景矩阵：
 * 1. 雨打芭蕉 (rain): 粉红噪音雨幕 + 泊松分布叶面滴落冲击瞬态 (下行滑音)
 * 2. 深山古寺暮钟 (temple): 6分音非谐波加法正弦矩阵 (130.8Hz基音+拍音) + 杵击瞬态 + 幽壑风籁
 * 3. 小桥流水 (creek): 双低频震荡器异步调制的带通湍流 + Minnaert气泡高频上扬脉冲
 */

export type SceneId = 'rain' | 'temple' | 'creek'

export interface SoundscapeState {
  isPlaying: boolean
  currentSceneId: SceneId | null
  volume: number
  isMuted: boolean
}

interface ActiveScene {
  id: SceneId
  sceneGain: GainNode
  stop: () => void
}

export class SoundscapeEngine {
  private audioCtx: AudioContext | null = null
  private masterGain: GainNode | null = null
  private activeScene: ActiveScene | null = null
  private currentSceneId: SceneId | null = null
  private volume: number = 0.6
  private isMuted: boolean = false
  private isPlaying: boolean = false
  private duckingFactor: number = 1.0

  private readonly CROSSFADE_SEC = 1.2

  constructor() {
    // 延迟初始化 AudioContext，避免在无用户手势时触发浏览器 Autoplay 拦截警告
  }

  /**
   * 初始化或唤醒 AudioContext 单例
   */
  public getAudioContext(): AudioContext | null {
    if (this.audioCtx) return this.audioCtx

    const AudioContextClass =
      typeof window !== 'undefined'
        ? window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
        : null

    if (!AudioContextClass) {
      return null
    }

    try {
      this.audioCtx = new AudioContextClass()
      this.masterGain = this.audioCtx.createGain()
      this.applyMasterGain(true)
      this.masterGain.connect(this.audioCtx.destination)
    } catch (e) {
      console.warn('[SoundscapeEngine] Failed to initialize AudioContext:', e)
    }

    return this.audioCtx
  }

  /**
   * 确保 AudioContext 进入 running 状态（浏览器自动播放策略门禁唤醒）
   */
  private async ensureRunning(): Promise<boolean> {
    const ctx = this.getAudioContext()
    if (!ctx) return false

    if (ctx.state === 'suspended') {
      try {
        await ctx.resume()
      } catch (e) {
        console.warn('[SoundscapeEngine] AudioContext resume failed:', e)
        return false
      }
    }
    return ctx.state === 'running'
  }

  /**
   * 播放指定意境场景（如未指定则延续当前场景或默认 rain）
   */
  public async play(sceneId?: SceneId): Promise<void> {
    const targetSceneId = sceneId || this.currentSceneId || 'rain'
    const ctx = this.getAudioContext()
    if (!ctx) return

    await this.ensureRunning()

    this.isPlaying = true

    if (this.activeScene && this.activeScene.id === targetSceneId) {
      // 当前场景已在运行，确保音量正常
      this.applyMasterGain()
      return
    }

    await this.switchScene(targetSceneId)
  }

  /**
   * 暂停伴读音效播放
   */
  public pause(): void {
    if (!this.isPlaying) return
    this.isPlaying = false

    if (this.activeScene && this.audioCtx && this.masterGain) {
      const now = this.audioCtx.currentTime
      // 快速淡出至静音，然后停止节点，防止粗暴截断导致的爆音
      this.masterGain.gain.cancelScheduledValues(now)
      this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now)
      this.masterGain.gain.linearRampToValueAtTime(0.0001, now + 0.2)

      const sceneToStop = this.activeScene
      this.activeScene = null

      setTimeout(() => {
        sceneToStop.stop()
        if (this.audioCtx && this.audioCtx.state === 'running') {
          // 暂停声卡句柄，降低 CPU 消耗
          try {
            const res = this.audioCtx.suspend()
            if (res && typeof res.catch === 'function') res.catch(() => {})
          } catch (_) {}
        }
      }, 250)
    }
  }

  /**
   * 切换意境场景（支持 1.2s 交叉淡入淡出，消除杂音裂隙）
   */
  public async setScene(sceneId: SceneId): Promise<void> {
    this.currentSceneId = sceneId
    if (this.isPlaying) {
      await this.switchScene(sceneId)
    }
  }

  /**
   * 调节主音量 (0.0 ~ 1.0)
   */
  public setVolume(vol: number): void {
    this.volume = Math.max(0, Math.min(1, vol))
    this.applyMasterGain()
  }

  /**
   * 设置静音开关
   */
  public setMuted(muted: boolean): void {
    this.isMuted = muted
    this.applyMasterGain()
  }

  /**
   * 闪避控制（用于朗诵语音播放时背景白噪音自动优雅淡降至 25%）
   */
  public setDucking(active: boolean): void {
    this.duckingFactor = active ? 0.25 : 1.0
    this.applyMasterGain()
  }

  /**
   * 获取当前引擎内部状态
   */
  public getState(): SoundscapeState {
    return {
      isPlaying: this.isPlaying,
      currentSceneId: this.currentSceneId,
      volume: this.volume,
      isMuted: this.isMuted,
    }
  }

  /**
   * 销毁引擎实例，释放声卡节点与定时器
   */
  public destroy(): void {
    this.pause()
    if (this.audioCtx) {
      try {
        const res = this.audioCtx.close()
        if (res && typeof res.catch === 'function') res.catch(() => {})
      } catch (_) {}
      this.audioCtx = null
      this.masterGain = null
    }
  }

  // ==========================================
  // 私有核心：场景切换与平滑淡入淡出 (Cross-fade)
  // ==========================================

  private async switchScene(sceneId: SceneId): Promise<void> {
    const ctx = this.getAudioContext()
    if (!ctx || !this.masterGain) return

    await this.ensureRunning()
    this.currentSceneId = sceneId
    this.applyMasterGain()

    const now = ctx.currentTime
    const oldScene = this.activeScene

    // 创建新场景实例（初始增益设为 0）
    const newSceneGain = ctx.createGain()
    newSceneGain.gain.setValueAtTime(0.0001, now)
    newSceneGain.connect(this.masterGain)

    const newSceneStopFn = this.buildSceneGraph(sceneId, ctx, newSceneGain)

    const newScene: ActiveScene = {
      id: sceneId,
      sceneGain: newSceneGain,
      stop: newSceneStopFn,
    }
    this.activeScene = newScene

    // 1.2s 对数/线性平滑淡入新场景
    newSceneGain.gain.linearRampToValueAtTime(1.0, now + this.CROSSFADE_SEC)

    // 旧场景平滑淡出并解绑节点
    if (oldScene) {
      try {
        oldScene.sceneGain.gain.cancelScheduledValues(now)
        oldScene.sceneGain.gain.setValueAtTime(oldScene.sceneGain.gain.value, now)
        oldScene.sceneGain.gain.linearRampToValueAtTime(0.0001, now + this.CROSSFADE_SEC)
      } catch (e) {
        console.warn('[SoundscapeEngine] Crossfade old scene gain ramp error:', e)
      }

      setTimeout(() => {
        oldScene.stop()
        try {
          oldScene.sceneGain.disconnect()
        } catch (_) {}
      }, (this.CROSSFADE_SEC + 0.1) * 1000)
    }
  }

  private applyMasterGain(immediate: boolean = false): void {
    if (!this.masterGain || !this.audioCtx) return

    const effectiveGain = this.isMuted ? 0 : this.volume * this.duckingFactor
    const now = this.audioCtx.currentTime

    try {
      this.masterGain.gain.cancelScheduledValues(now)
      if (immediate) {
        this.masterGain.gain.setValueAtTime(effectiveGain, now)
      } else {
        this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now)
        this.masterGain.gain.linearRampToValueAtTime(effectiveGain, now + 0.08)
      }
    } catch (e) {
      this.masterGain.gain.value = effectiveGain
    }
  }

  // ==========================================
  // 私有核心：三大古典意境 DSP 拓扑构建
  // ==========================================

  private buildSceneGraph(sceneId: SceneId, ctx: AudioContext, destination: AudioNode): () => void {
    switch (sceneId) {
      case 'rain':
        return this.createRainScene(ctx, destination)
      case 'temple':
        return this.createTempleBellScene(ctx, destination)
      case 'creek':
        return this.createCreekScene(ctx, destination)
      default:
        return this.createRainScene(ctx, destination)
    }
  }

  /**
   * 场景一：雨打芭蕉 (Rain on Banana Leaves)
   * - 连续粉红噪音雨幕 + 0.12Hz 微风动态呼吸 LFO
   * - 泊松分布触发的叶面滴答水滴冲击（520Hz~680Hz 快速下探至 200Hz）+ 立体声相环绕
   */
  private createRainScene(ctx: AudioContext, destination: AudioNode): () => void {
    let isAlive = true
    const cleanups: Array<() => void> = []

    // 1. 雨幕层 (Pink Noise)
    const noiseBuffer = this.generatePinkNoiseBuffer(ctx, 4.0)
    const noiseSource = ctx.createBufferSource()
    noiseSource.buffer = noiseBuffer
    noiseSource.loop = true

    // 低通滤波模拟漫天细雨
    const rainFilter = ctx.createBiquadFilter()
    rainFilter.type = 'lowpass'
    rainFilter.frequency.setValueAtTime(1100, ctx.currentTime)
    rainFilter.Q.setValueAtTime(0.7, ctx.currentTime)

    // 微风低频振荡器 (LFO)
    const lfo = ctx.createOscillator()
    const lfoGain = ctx.createGain()
    lfo.frequency.setValueAtTime(0.12, ctx.currentTime)
    lfoGain.gain.setValueAtTime(220, ctx.currentTime) // +/- 220Hz 调制滤波截止频率
    lfo.connect(lfoGain)
    lfoGain.connect(rainFilter.frequency)

    const rainGain = ctx.createGain()
    rainGain.gain.setValueAtTime(0.35, ctx.currentTime)

    noiseSource.connect(rainFilter)
    rainFilter.connect(rainGain)
    rainGain.connect(destination)

    noiseSource.start()
    lfo.start()

    cleanups.push(() => {
      try {
        noiseSource.stop()
        noiseSource.disconnect()
        lfo.stop()
        lfo.disconnect()
        lfoGain.disconnect()
        rainFilter.disconnect()
        rainGain.disconnect()
      } catch (_) {}
    })

    // 2. 芭蕉叶滴落层 (Droplet Impulses)
    let dropletTimer: ReturnType<typeof setTimeout> | null = null

    const scheduleNextDroplet = () => {
      if (!isAlive) return
      // 泊松随机间隔 (180ms ~ 450ms)
      const nextDelay = 180 + Math.random() * 270
      dropletTimer = setTimeout(() => {
        if (!isAlive) return
        this.triggerRainDroplet(ctx, destination)
        scheduleNextDroplet()
      }, nextDelay)
    }

    scheduleNextDroplet()

    cleanups.push(() => {
      if (dropletTimer) clearTimeout(dropletTimer)
    })

    return () => {
      isAlive = false
      cleanups.forEach((fn) => fn())
    }
  }

  private triggerRainDroplet(ctx: AudioContext, destination: AudioNode): void {
    if (ctx.state !== 'running') return
    const now = ctx.currentTime

    try {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const panner = this.createPanner(ctx, (Math.random() * 1.2) - 0.6)

      const startFreq = 520 + Math.random() * 160
      const endFreq = 190 + Math.random() * 40
      const duration = 0.045 + Math.random() * 0.015

      osc.type = 'sine'
      osc.frequency.setValueAtTime(startFreq, now)
      osc.frequency.exponentialRampToValueAtTime(endFreq, now + duration)

      gain.gain.setValueAtTime(0.0001, now)
      gain.gain.linearRampToValueAtTime(0.18 + Math.random() * 0.08, now + 0.004)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + duration)

      osc.connect(gain)
      gain.connect(panner)
      panner.connect(destination)

      osc.start(now)
      osc.stop(now + duration + 0.01)

      setTimeout(() => {
        try {
          osc.disconnect()
          gain.disconnect()
          panner.disconnect()
        } catch (_) {}
      }, (duration + 0.05) * 1000)
    } catch (_) {}
  }

  /**
   * 场景二：深山古寺暮钟 (Mountain Temple Evening Bell)
   * - 6组非谐波分音加法正弦矩阵 (130.8Hz基音，长达8s的指数衰减，带微小detune拍音)
   * - 木杵叩钟瞬态质感脉冲 (180Hz带通木质共振)
   * - 深山幽夜微弱背景空气感 (110Hz微共鸣)
   * - 周期性悠长敲响 (每 10 秒敲响一杵)
   */
  private createTempleBellScene(ctx: AudioContext, destination: AudioNode): () => void {
    let isAlive = true
    const cleanups: Array<() => void> = []

    // 1. 空山微弱夜籁背景
    const ambientNoise = this.generatePinkNoiseBuffer(ctx, 3.0)
    const ambientSource = ctx.createBufferSource()
    ambientSource.buffer = ambientNoise
    ambientSource.loop = true

    const ambientFilter = ctx.createBiquadFilter()
    ambientFilter.type = 'bandpass'
    ambientFilter.frequency.setValueAtTime(110, ctx.currentTime)
    ambientFilter.Q.setValueAtTime(2.5, ctx.currentTime)

    const ambientGain = ctx.createGain()
    ambientGain.gain.setValueAtTime(0.04, ctx.currentTime)

    ambientSource.connect(ambientFilter)
    ambientFilter.connect(ambientGain)
    ambientGain.connect(destination)

    ambientSource.start()

    cleanups.push(() => {
      try {
        ambientSource.stop()
        ambientSource.disconnect()
        ambientFilter.disconnect()
        ambientGain.disconnect()
      } catch (_) {}
    })

    // 2. 钟声触发逻辑与调度器
    const strike = () => {
      if (!isAlive || ctx.state !== 'running') return
      this.strikeTempleBell(ctx, destination)
    }

    // 立即敲击第一响
    strike()

    // 随后每 10 秒敲击一次（余音袅袅）
    const bellInterval = setInterval(() => {
      if (!isAlive) return
      strike()
    }, 10000)

    cleanups.push(() => {
      clearInterval(bellInterval)
    })

    return () => {
      isAlive = false
      cleanups.forEach((fn) => fn())
    }
  }

  /**
   * 敲响一次大铜钟 (6组非谐波加法合成分音 + 杵击瞬态)
   */
  public strikeTempleBell(ctx: AudioContext, destination: AudioNode): void {
    const now = ctx.currentTime

    // 6组detuned非谐波分音配置
    const partials = [
      { freq: 130.8, detune: 0.4, amp: 0.35, decay: 7.5 },
      { freq: 65.4, detune: -0.3, amp: 0.28, decay: 8.8 },
      { freq: 155.7, detune: 0.8, amp: 0.22, decay: 5.0 },
      { freq: 198.8, detune: -0.6, amp: 0.18, decay: 4.2 },
      { freq: 262.9, detune: 1.1, amp: 0.14, decay: 3.0 },
      { freq: 358.4, detune: -0.9, amp: 0.08, decay: 1.8 },
    ]

    partials.forEach((p) => {
      try {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.setValueAtTime(p.freq + p.detune, now)

        gain.gain.setValueAtTime(0.0001, now)
        gain.gain.linearRampToValueAtTime(p.amp, now + 0.02)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + p.decay)

        osc.connect(gain)
        gain.connect(destination)

        osc.start(now)
        osc.stop(now + p.decay + 0.05)

        setTimeout(() => {
          try {
            osc.disconnect()
            gain.disconnect()
          } catch (_) {}
        }, (p.decay + 0.1) * 1000)
      } catch (_) {}
    })

    // 木杵叩击木质瞬态 (Wood strike transient)
    try {
      const strikeOsc = ctx.createOscillator()
      const strikeFilter = ctx.createBiquadFilter()
      const strikeGain = ctx.createGain()

      strikeOsc.type = 'triangle'
      strikeOsc.frequency.setValueAtTime(180, now)

      strikeFilter.type = 'bandpass'
      strikeFilter.frequency.setValueAtTime(180, now)
      strikeFilter.Q.setValueAtTime(2.5, now)

      strikeGain.gain.setValueAtTime(0.0001, now)
      strikeGain.gain.linearRampToValueAtTime(0.25, now + 0.004)
      strikeGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.045)

      strikeOsc.connect(strikeFilter)
      strikeFilter.connect(strikeGain)
      strikeGain.connect(destination)

      strikeOsc.start(now)
      strikeOsc.stop(now + 0.05)

      setTimeout(() => {
        try {
          strikeOsc.disconnect()
          strikeFilter.disconnect()
          strikeGain.disconnect()
        } catch (_) {}
      }, 100)
    } catch (_) {}
  }

  /**
   * 场景三：小桥流水 (Flowing Creek Stream)
   * - 带通中频流水湍流 + 双低频振荡器异步调制 (0.14Hz & 0.35Hz 浪涌动态)
   * - Minnaert 气泡共振音 (400Hz~600Hz 向上扫频至 900Hz~1300Hz 的快速阻尼正弦)
   */
  private createCreekScene(ctx: AudioContext, destination: AudioNode): () => void {
    let isAlive = true
    const cleanups: Array<() => void> = []

    // 1. 水流湍流基底 (Pink Noise + Bandpass Filter)
    const streamBuffer = this.generatePinkNoiseBuffer(ctx, 3.5)
    const streamSource = ctx.createBufferSource()
    streamSource.buffer = streamBuffer
    streamSource.loop = true

    const streamFilter = ctx.createBiquadFilter()
    streamFilter.type = 'bandpass'
    streamFilter.frequency.setValueAtTime(850, ctx.currentTime)
    streamFilter.Q.setValueAtTime(1.2, ctx.currentTime)

    // 异步双 LFO 调制：模拟溪流奔涌的强弱起伏
    const lfo1 = ctx.createOscillator()
    const lfo1Gain = ctx.createGain()
    lfo1.frequency.setValueAtTime(0.14, ctx.currentTime)
    lfo1Gain.gain.setValueAtTime(140, ctx.currentTime) // 调制带通中心频率 +/- 140Hz
    lfo1.connect(lfo1Gain)
    lfo1Gain.connect(streamFilter.frequency)

    const streamGain = ctx.createGain()
    streamGain.gain.setValueAtTime(0.28, ctx.currentTime)

    const lfo2 = ctx.createOscillator()
    const lfo2Gain = ctx.createGain()
    lfo2.frequency.setValueAtTime(0.35, ctx.currentTime)
    lfo2Gain.gain.setValueAtTime(0.05, ctx.currentTime) // 调制音量 +/- 0.05
    lfo2.connect(lfo2Gain)
    lfo2Gain.connect(streamGain.gain)

    streamSource.connect(streamFilter)
    streamFilter.connect(streamGain)
    streamGain.connect(destination)

    streamSource.start()
    lfo1.start()
    lfo2.start()

    cleanups.push(() => {
      try {
        streamSource.stop()
        streamSource.disconnect()
        lfo1.stop()
        lfo1.disconnect()
        lfo1Gain.disconnect()
        lfo2.stop()
        lfo2.disconnect()
        lfo2Gain.disconnect()
        streamFilter.disconnect()
        streamGain.disconnect()
      } catch (_) {}
    })

    // 2. Minnaert 气泡咕噜音调度器 (4 ~ 8 次/秒)
    let bubbleTimer: ReturnType<typeof setTimeout> | null = null

    const scheduleBubble = () => {
      if (!isAlive) return
      const nextDelay = 120 + Math.random() * 140
      bubbleTimer = setTimeout(() => {
        if (!isAlive) return
        this.triggerMinnaertBubble(ctx, destination)
        scheduleBubble()
      }, nextDelay)
    }

    scheduleBubble()

    cleanups.push(() => {
      if (bubbleTimer) clearTimeout(bubbleTimer)
    })

    return () => {
      isAlive = false
      cleanups.forEach((fn) => fn())
    }
  }

  private triggerMinnaertBubble(ctx: AudioContext, destination: AudioNode): void {
    if (ctx.state !== 'running') return
    const now = ctx.currentTime

    try {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const panner = this.createPanner(ctx, (Math.random() * 1.4) - 0.7)

      const startFreq = 420 + Math.random() * 180
      const endFreq = startFreq + 500 + Math.random() * 320
      const duration = 0.026 + Math.random() * 0.01

      osc.type = 'sine'
      osc.frequency.setValueAtTime(startFreq, now)
      // 频率向上滑移
      osc.frequency.linearRampToValueAtTime(endFreq, now + duration)

      gain.gain.setValueAtTime(0.0001, now)
      gain.gain.linearRampToValueAtTime(0.12, now + 0.003)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + duration)

      osc.connect(gain)
      gain.connect(panner)
      panner.connect(destination)

      osc.start(now)
      osc.stop(now + duration + 0.01)

      setTimeout(() => {
        try {
          osc.disconnect()
          gain.disconnect()
          panner.disconnect()
        } catch (_) {}
      }, (duration + 0.05) * 1000)
    } catch (_) {}
  }

  // ==========================================
  // 辅助 DSP 算法：立体声相与粉红噪音缓冲
  // ==========================================

  private createPanner(ctx: AudioContext, panVal: number): AudioNode {
    if (typeof ctx.createStereoPanner === 'function') {
      const panner = ctx.createStereoPanner()
      panner.pan.setValueAtTime(Math.max(-1, Math.min(1, panVal)), ctx.currentTime)
      return panner
    }
    // 兼容不支持 StereoPannerNode 的最小环境
    const fallback = ctx.createGain()
    fallback.gain.setValueAtTime(1.0, ctx.currentTime)
    return fallback
  }

  /**
   * 生成立体声粉红噪音缓冲 (Paul Kellet 3-pole 滤波器算法)
   */
  private generatePinkNoiseBuffer(ctx: AudioContext, seconds: number = 3.0): AudioBuffer {
    const sampleRate = ctx.sampleRate || 44100
    const bufferSize = Math.floor(sampleRate * seconds)
    const buffer = ctx.createBuffer(2, bufferSize, sampleRate)

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel)
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0

      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.96900 * b2 + white * 0.1538520
        b3 = 0.86650 * b3 + white * 0.3104856
        b4 = 0.55000 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.0168980
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11
        b6 = white * 0.115926
      }
    }

    return buffer
  }
}

/**
 * 伴读音效引擎全局单例
 */
export const soundscapeEngine = new SoundscapeEngine()
