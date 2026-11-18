<template>
  <div class="soundscape-container">
    <!-- 折叠态：44px 雅致金玉微型浮盘 -->
    <transition name="disc-fade">
      <button
        v-if="!store.isExpanded"
        class="soundscape-disc"
        :class="{ 'is-playing': store.isPlaying }"
        type="button"
        title="诗境伴读"
        aria-label="开启或收起诗境伴读"
        @click="store.toggleExpand"
      >
        <!-- 动态呼吸光晕环 -->
        <span v-if="store.isPlaying" class="disc-ripple" />

        <!-- 当前意境单线矢量图标 -->
        <span class="disc-icon">
          <svg v-if="store.currentSceneId === 'rain'" viewBox="0 0 24 24" fill="none" stroke="currentColor" class="svg-icon">
            <!-- 雨打芭蕉：芭蕉叶 + 细雨丝 -->
            <path d="M12 21C7 21 3 17 3 12C3 7 7 3 12 3C17 3 21 7 21 12" stroke-width="1.6" stroke-linecap="round" />
            <path d="M12 3C12 9 8 13 3 14" stroke-width="1.6" stroke-linecap="round" />
            <line x1="16" y1="13" x2="14" y2="16" stroke-width="1.6" stroke-linecap="round" />
            <line x1="20" y1="15" x2="18" y2="18" stroke-width="1.6" stroke-linecap="round" />
            <line x1="15" y1="19" x2="13" y2="22" stroke-width="1.6" stroke-linecap="round" />
          </svg>

          <svg v-else-if="store.currentSceneId === 'temple'" viewBox="0 0 24 24" fill="none" stroke="currentColor" class="svg-icon">
            <!-- 古寺暮钟：梵钟轮廓 + 钟纽 + 撞点 -->
            <path d="M12 3V5" stroke-width="1.6" stroke-linecap="round" />
            <path d="M6 19H18C17 14 17 8 12 8C7 8 7 14 6 19Z" stroke-width="1.6" stroke-linejoin="round" />
            <path d="M5 19H19" stroke-width="1.6" stroke-linecap="round" />
            <circle cx="12" cy="14" r="1.5" fill="currentColor" />
          </svg>

          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" class="svg-icon">
            <!-- 小桥流水：拱桥 + 流水波纹 -->
            <path d="M3 12C6 8 18 8 21 12" stroke-width="1.6" stroke-linecap="round" />
            <path d="M7 11V14" stroke-width="1.4" stroke-linecap="round" />
            <path d="M17 11V14" stroke-width="1.4" stroke-linecap="round" />
            <path d="M2 17C4.5 16 7.5 18 10 17C12.5 16 15.5 18 18 17C20.5 16 22 17 22 17" stroke-width="1.5" stroke-linecap="round" />
            <path d="M4 20C6.5 19 9.5 21 12 20C14.5 19 17.5 21 20 20" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </span>

        <!-- 播放时微型波形提示 -->
        <span v-if="store.isPlaying" class="disc-bars">
          <i class="bar b1" />
          <i class="bar b2" />
          <i class="bar b3" />
        </span>
      </button>
    </transition>

    <!-- 展开态：280px 墨夜古典卷轴微卡片 -->
    <transition name="panel-slide">
      <div
        v-if="store.isExpanded"
        class="soundscape-panel"
        role="region"
        aria-label="诗境伴读控制器"
      >
        <!-- 面板顶部：标题与收起键 -->
        <div class="panel-header">
          <div class="header-title">
            <span class="gold-seal-dot" />
            <span class="title-text">诗境伴读</span>
          </div>
          <button
            class="header-btn"
            type="button"
            title="收起微卡片"
            aria-label="收起"
            @click="store.toggleExpand"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class="mini-icon">
              <path d="M18 12H6" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </button>
        </div>

        <!-- 意境场景选项卡 -->
        <div class="scene-tabs" role="tablist">
          <button
            v-for="scene in SCENES"
            :key="scene.id"
            class="scene-tab-item"
            :class="{ active: store.currentSceneId === scene.id }"
            type="button"
            role="tab"
            :aria-selected="store.currentSceneId === scene.id"
            @click="store.setScene(scene.id)"
          >
            <span class="tab-name">{{ scene.name }}</span>
          </button>
        </div>

        <!-- 当前场景副题与意境韵律 -->
        <div class="scene-meta">
          <span class="scene-subtext">{{ currentSceneInfo?.subText }}</span>
          <div class="sound-wave" :class="{ active: store.isPlaying }">
            <span class="wave-bar w1" />
            <span class="wave-bar w2" />
            <span class="wave-bar w3" />
            <span class="wave-bar w4" />
          </div>
        </div>

        <!-- 主控制区：播放/暂停核心按钮 -->
        <div class="panel-action">
          <button
            class="play-toggle-btn"
            :class="{ playing: store.isPlaying }"
            type="button"
            :title="store.isPlaying ? '暂停伴读' : '启幕伴读'"
            :aria-label="store.isPlaying ? '暂停' : '播放'"
            @click="store.togglePlay"
          >
            <svg v-if="!store.isPlaying" viewBox="0 0 24 24" fill="currentColor" class="play-icon">
              <polygon points="8,5 19,12 8,19" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor" class="play-icon">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          </button>
        </div>

        <!-- 底部控制：音量滑杆与静音按钮 -->
        <div class="panel-volume-row">
          <button
            class="mute-btn"
            type="button"
            :title="store.isMuted ? '取消静音' : '静音'"
            :aria-label="store.isMuted ? '取消静音' : '静音'"
            @click="store.toggleMute"
          >
            <svg v-if="store.isMuted || store.volume === 0" viewBox="0 0 24 24" fill="none" stroke="currentColor" class="mini-icon">
              <path d="M11 5L6 9H2V15H6L11 19V5Z" stroke-width="1.6" stroke-linejoin="round" />
              <line x1="23" y1="9" x2="17" y2="15" stroke-width="1.6" stroke-linecap="round" />
              <line x1="17" y1="9" x2="23" y2="15" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <svg v-else-if="store.volume < 50" viewBox="0 0 24 24" fill="none" stroke="currentColor" class="mini-icon">
              <path d="M11 5L6 9H2V15H6L11 19V5Z" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M15.54 8.46C16.48 9.4 17 10.67 17 12C17 13.33 16.48 14.6 15.54 15.54" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" class="mini-icon">
              <path d="M11 5L6 9H2V15H6L11 19V5Z" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M15.54 8.46C16.48 9.4 17 10.67 17 12C17 13.33 16.48 14.6 15.54 15.54" stroke-width="1.6" stroke-linecap="round" />
              <path d="M19.07 4.93C20.95 6.8 22 9.34 22 12C22 14.66 20.95 17.2 19.07 19.07" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </button>

          <!-- 优雅金夜音量滑条 -->
          <div class="slider-wrapper">
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              :value="store.isMuted ? 0 : store.volume"
              class="volume-slider"
              aria-label="音量调节"
              @input="onSliderInput"
            />
          </div>

          <!-- 数值显示（tabular-nums 避免跳动） -->
          <span class="volume-value">
            {{ store.isMuted ? '静音' : `${store.volume}%` }}
          </span>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSoundscapeStore, SCENES } from '@/store/soundscape'

const store = useSoundscapeStore()

const currentSceneInfo = computed(() => {
  return SCENES.find((s) => s.id === store.currentSceneId) || SCENES[0]
})

const onSliderInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  const val = Number(target.value)
  store.setVolume(val)
}
</script>

<style scoped>
/* 容器常驻右下角，跨路由稳定悬浮 */
.soundscape-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  user-select: none;
  font-family: var(--f-sans, sans-serif);
}

/* ==========================================
   折叠态：44px 墨夜金印微型悬浮盘
   ========================================== */
.soundscape-disc {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--md-primary-container);
  border: 1.5px solid var(--md-outline-variant);
  color: var(--md-on-primary-container);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(12px);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
  padding: 0;
  outline: none;
}

.soundscape-disc:hover {
  transform: scale(1.06);
  border-color: var(--md-primary);
  box-shadow: var(--shadow-sm);
}

.soundscape-disc.is-playing {
  border-color: var(--md-primary);
  box-shadow: var(--shadow-sm);
}

.disc-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.svg-icon {
  width: 100%;
  height: 100%;
}

/* 播放呼吸波纹 */
.disc-ripple {
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  border-radius: 50%;
  border: 1px solid var(--md-outline-variant);
  animation: disc-breathe 2.4s infinite ease-out;
  pointer-events: none;
}

@keyframes disc-breathe {
  0% {
    transform: scale(0.95);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.15);
    opacity: 0.2;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}

/* 盘底微型跳动音波 */
.disc-bars {
  position: absolute;
  bottom: 4px;
  display: flex;
  gap: 2px;
  align-items: flex-end;
  height: 6px;
}

.disc-bars .bar {
  width: 2px;
  background-color: var(--md-primary);
  border-radius: 1px;
}

.disc-bars .b1 {
  height: 3px;
  animation: bar-dance 0.8s infinite alternate ease-in-out;
}
.disc-bars .b2 {
  height: 5px;
  animation: bar-dance 1.1s infinite alternate ease-in-out 0.2s;
}
.disc-bars .b3 {
  height: 4px;
  animation: bar-dance 0.9s infinite alternate ease-in-out 0.4s;
}

@keyframes bar-dance {
  0% {
    height: 2px;
  }
  100% {
    height: 6px;
  }
}

/* ==========================================
   展开态：280px 墨夜古典控制卡片
   ========================================== */
.soundscape-panel {
  width: min(320px, calc(100vw - 32px));
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: 28px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(16px);
  color: var(--md-on-surface);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 顶部栏 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--md-outline-variant);
  padding-bottom: 8px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gold-seal-dot {
  width: 6px;
  height: 6px;
  background: var(--md-primary);
  border-radius: 1px;
  transform: rotate(45deg);
}

.title-text {
  font-family: var(--f-sans);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: normal;
  color: var(--md-on-surface);
}

.header-btn {
  background: transparent;
  border: none;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  transition: color 160ms ease, background-color 160ms ease;
 min-width: 48px;  min-height: 48px; }

.header-btn:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container);
}

/* 场景三联签 */
.scene-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.scene-tab-item {
  background: var(--md-surface-container-lowest);
  border: 1px solid var(--md-outline-variant);
  border-radius: 999px;
  padding: 6px 0;
  text-align: center;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  transition: all 180ms ease;
  font-size: 13px;
  font-family: var(--f-sans);
 min-height: 44px; }

.scene-tab-item:hover {
  border-color: var(--md-outline-variant);
  color: var(--md-on-surface);
}

.scene-tab-item.active {
  background: var(--md-primary-container);
  font-weight: 500;
  color: var(--md-on-primary-container);
  border-color: var(--md-primary-container);
}

/* 场景副题与动效波 */
.scene-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 2px;
}

.scene-subtext {
  font-family: var(--f-sans);
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.sound-wave {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 12px;
  opacity: 0.3;
  transition: opacity 200ms ease;
}

.sound-wave.active {
  opacity: 1;
}

.wave-bar {
  width: 2px;
  background-color: var(--md-primary);
  border-radius: 1px;
}

.wave-bar.w1 {
  height: 4px;
}
.wave-bar.w2 {
  height: 8px;
}
.wave-bar.w3 {
  height: 11px;
}
.wave-bar.w4 {
  height: 6px;
}

.sound-wave.active .w1 {
  animation: wave-play 0.7s infinite alternate ease-in-out;
}
.sound-wave.active .w2 {
  animation: wave-play 1.1s infinite alternate ease-in-out 0.2s;
}
.sound-wave.active .w3 {
  animation: wave-play 0.9s infinite alternate ease-in-out 0.4s;
}
.sound-wave.active .w4 {
  animation: wave-play 0.8s infinite alternate ease-in-out 0.1s;
}

@keyframes wave-play {
  0% {
    height: 3px;
  }
  100% {
    height: 12px;
  }
}

/* 播放核心按钮 */
.panel-action {
  display: flex;
  justify-content: center;
  padding: 4px 0;
}

.play-toggle-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--md-primary-container);
  border: 1.5px solid var(--md-primary);
  color: var(--md-on-primary-container);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 180ms ease;
  outline: none;
}

.play-toggle-btn:hover {
  transform: scale(1.05);
  background: var(--md-primary-container);
  box-shadow: var(--shadow-sm);
}

.play-toggle-btn.playing {
  background: var(--md-primary);
  color: var(--md-on-primary);
  border-color: var(--md-primary);
}

.play-toggle-btn.playing:hover {
  box-shadow: var(--shadow-sm);
  background: var(--md-primary);
  color: var(--md-on-primary);
}

.play-icon {
  width: 18px;
  height: 18px;
}

/* 底部音量调节排 */
.panel-volume-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--md-surface-container-high);
  border-radius: 16px;
  padding: 0 8px 0 0;
}

.mute-btn {
  background: transparent;
  border: none;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 160ms ease;
 min-width: 48px;  min-height: 48px;  border-radius: 999px; }

.mute-btn:hover {
  color: var(--md-on-surface);
}

.mini-icon {
  width: 16px;
  height: 16px;
}

.slider-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
}

/* 自定义流金音量滑杆 */
.volume-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 4px;
  background: var(--md-surface-container);
  border-radius: 12px;
  outline: none;
  cursor: pointer;
}

.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--md-primary);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: transform 140ms ease;
}

.volume-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.volume-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--md-primary);
  border: none;
  cursor: pointer;
}

.volume-value {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--md-on-surface-variant);
  min-width: 30px;
  text-align: right;
}

/* ==========================================
   动画与无障碍动效降级
   ========================================== */
.disc-fade-enter-active,
.disc-fade-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.disc-fade-enter-from,
.disc-fade-leave-to {
  opacity: 0;
  transform: scale(0.85);
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 200ms ease, transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}

@media (prefers-reduced-motion: reduce) {
  .soundscape-disc,
  .disc-ripple,
  .disc-bars .bar,
  .sound-wave .wave-bar,
  .play-toggle-btn,
  .volume-slider::-webkit-slider-thumb {
    animation: none !important;
    transition: none !important;
  }
}

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.volume-slider { height: 44px; background: linear-gradient(var(--md-outline), var(--md-outline)) center / 100% 4px no-repeat; } .volume-slider::-webkit-slider-thumb { width: 20px; height: 20px; } .volume-slider::-moz-range-thumb { width: 20px; height: 20px; } .soundscape-disc:focus-visible, .header-btn:focus-visible, .scene-tab-item:focus-visible, .play-toggle-btn:focus-visible, .mute-btn:focus-visible, .volume-slider:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; } @media (max-width: 600px) { .soundscape-container { bottom: 16px; right: 16px; } }
</style>
