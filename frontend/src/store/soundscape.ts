import { defineStore } from 'pinia'
import { ref } from 'vue'
import { soundscapeEngine, type SceneId } from '@/utils/soundscapeEngine'

export interface SoundscapeScene {
  id: SceneId
  name: string
  subText: string
  icon: string
}

export const SCENES: SoundscapeScene[] = [
  { id: 'rain', name: '雨打芭蕉', subText: '空山新雨 · 淅沥芭蕉', icon: 'rain' },
  { id: 'temple', name: '古寺暮钟', subText: '云岫梵音 · 暮鼓晨钟', icon: 'bell' },
  { id: 'creek', name: '小桥流水', subText: '石上清泉 · 潺潺弄玉', icon: 'creek' },
]

export const useSoundscapeStore = defineStore(
  'soundscape',
  () => {
    // 运行态状态（严禁持久化到 localStorage，遵守浏览器自动播放限制）
    const isPlaying = ref<boolean>(false)

    // 用户偏好状态（通过 pinia-plugin-persistedstate 持久化存储）
    const currentSceneId = ref<SceneId>('rain')
    const volume = ref<number>(60) // 0 ~ 100
    const isMuted = ref<boolean>(false)
    const isExpanded = ref<boolean>(false)

    /**
     * 播放/暂停控制切换
     */
    const togglePlay = async () => {
      if (isPlaying.value) {
        isPlaying.value = false
        soundscapeEngine.pause()
      } else {
        isPlaying.value = true
        soundscapeEngine.setVolume(volume.value / 100)
        soundscapeEngine.setMuted(isMuted.value)
        await soundscapeEngine.play(currentSceneId.value)
      }
    }

    /**
     * 明确暂停
     */
    const pause = () => {
      if (isPlaying.value) {
        isPlaying.value = false
        soundscapeEngine.pause()
      }
    }

    /**
     * 切换意境场景
     */
    const setScene = async (id: SceneId) => {
      currentSceneId.value = id
      if (isPlaying.value) {
        await soundscapeEngine.setScene(id)
      }
    }

    /**
     * 调节音量 (0 ~ 100)
     */
    const setVolume = (num: number) => {
      const clamped = Math.max(0, Math.min(100, Math.round(num)))
      volume.value = clamped
      if (isMuted.value && clamped > 0) {
        isMuted.value = false
      }
      soundscapeEngine.setVolume(clamped / 100)
      soundscapeEngine.setMuted(isMuted.value)
    }

    /**
     * 切换静音
     */
    const toggleMute = () => {
      isMuted.value = !isMuted.value
      soundscapeEngine.setMuted(isMuted.value)
    }

    /**
     * 展开/收起控制面板
     */
    const toggleExpand = () => {
      isExpanded.value = !isExpanded.value
    }

    const setExpanded = (expanded: boolean) => {
      isExpanded.value = expanded
    }

    return {
      // 状态
      isPlaying,
      currentSceneId,
      volume,
      isMuted,
      isExpanded,
      // 动作
      togglePlay,
      pause,
      setScene,
      setVolume,
      toggleMute,
      toggleExpand,
      setExpanded,
    }
  },
  {
    persist: {
      // 严格仅持久化偏好项，严禁持久化 isPlaying: true（防冷启动自动播放报错）
      pick: ['volume', 'currentSceneId', 'isMuted', 'isExpanded'],
    },
  },
)
